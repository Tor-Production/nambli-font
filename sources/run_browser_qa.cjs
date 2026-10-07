// Copyright 2026 The Nambli Project Authors. SPDX-License-Identifier: OFL-1.1
// Explicit automated regression harness, not access to the user's browser profile.
const fs = require('node:fs');
const path = require('node:path');
const http = require('node:http');
const crypto = require('node:crypto');
const {createRequire} = require('node:module');
const args = Object.fromEntries(process.argv.slice(2).reduce((a,v,i,all) => i%2 ? a : [...a,[v.slice(2),all[i+1]]], []));
if (!args.fixture || !args.output) throw new Error('Usage: --fixture DIR --output NEW_DIR [--playwright-module PATH] [--webkit-executable PATH]');
const root = path.resolve(args.fixture), out=path.resolve(args.output);
fs.mkdirSync(out, {recursive:false});
const pw = args['playwright-module'] ? require(args['playwright-module']) : require('playwright');
const manifest = JSON.parse(fs.readFileSync(path.join(root,'manifest.json')));
const faces=[...new Set(manifest.shape_results.map(r=>r.face))];
const requests=[];
const server=http.createServer((req,res)=>{
  const name=decodeURIComponent(req.url.split('?')[0]);
  const file=path.resolve(root,'.'+name);
  if (!file.startsWith(root+path.sep) || !fs.existsSync(file)) {res.writeHead(404);res.end();return;}
  requests.push(name);
  res.setHeader('Content-Type',file.endsWith('.woff2')?'font/woff2':file.endsWith('.css')?'text/css':file.endsWith('.json')?'application/json':'text/html; charset=utf-8');
  res.end(fs.readFileSync(file));
});
async function test(engine, config={}) {
  const result={engine,status:'NOT TESTED',versions:{playwright:require(path.join(path.dirname(require.resolve(args['playwright-module']||'playwright')),'package.json')).version},
    checks:[],platform_font_diagnostics:[],responses:[],page_errors:[]};
  let browser;
  try {
    browser=await pw[engine].launch({headless:true,...config});
    result.versions.browser=browser.version();
    const page=await browser.newPage({viewport:{width:1600,height:980},deviceScaleFactor:1});
    page.on('pageerror',e=>result.page_errors.push(String(e)));
    page.on('response',r=>{if(r.url().endsWith('.woff2')) result.responses.push({file:new URL(r.url()).pathname,status:r.status()});});
    await page.goto(`http://127.0.0.1:${server.address().port}/Nambli-Subset-Review.html`);
    await page.waitForFunction(()=>window.qaReady===true && !!window.corpus);
    for (const face of faces) {
      await page.evaluate(face=>setFace(face),face);
      const checks=await page.evaluate(async face=>{
        const checks=[];
        const variants=['full','baseline','ext-only','patched','coherent'];
        for (const sample of window.corpus.samples) {
          // Like tofu/HarfBuzz, compare one logical line. Raw LF is retained in corpus.
          const text=sample.text.replaceAll('\n','');
          for(const v of variants) await document.fonts.load(`42px "${face}-${v}"`,text);
          await document.fonts.ready;
          const measure=document.createElement('canvas').getContext('2d');
          measure.font=`42px "${face}-full"`;
          const width=Math.ceil(measure.measureText(text).width)+100;
          if(width>32760) throw new Error('Canvas width exceeds tested limit: '+sample.id);
          function draw(v) {
            const c=document.createElement('canvas');c.width=width;c.height=180;
            const ctx=c.getContext('2d',{willReadFrequently:true});ctx.fillStyle='white';ctx.fillRect(0,0,width,180);
            ctx.fillStyle='black';ctx.font=`42px "${face}-${v}"`;ctx.textBaseline='alphabetic';
            ctx.fillText(text,40,110);
            return {width:ctx.measureText(text).width,pixels:ctx.getImageData(0,0,width,180).data};
          }
          const ref=draw('full');
          const outcomes={};
          for(const v of variants.slice(1)) {
            const got=draw(v);let pixels=0;
            for(let i=0;i<ref.pixels.length;i+=4) if(ref.pixels[i]!==got.pixels[i] || ref.pixels[i+1]!==got.pixels[i+1] || ref.pixels[i+2]!==got.pixels[i+2]) pixels++;
            outcomes[v]={different_pixels:pixels,advance_delta:got.width-ref.width};
          }
          checks.push({face,sample:sample.id,outcomes});
        }
        return checks;
      },face);
      result.checks.push(...checks);
      if (face==='Nambli-Regular' || face==='Nambli-Italic') {
        await page.screenshot({path:path.join(out,`${engine}-${face}.png`)});
        if(engine==='chromium') {
          const session=await page.context().newCDPSession(page);
          await session.send('DOM.enable');await session.send('CSS.enable');
          const {root}=await session.send('DOM.getDocument');
          const {nodeIds}=await session.send('DOM.querySelectorAll',{nodeId:root.nodeId,selector:'td.sample'});
          const labels=await page.locator('td.sample').evaluateAll(nodes=>nodes.slice(0,12).map(el=>({sample:el.parentElement.dataset.sample,variant:el.dataset.variant})));
          for(const [index,nodeId] of nodeIds.slice(0,12).entries()) {
            const diagnostics=await session.send('CSS.getPlatformFontsForNode',{nodeId});
            result.platform_font_diagnostics.push({face,nodeId,...labels[index],...diagnostics});
          }
          await session.detach();
        }
      }
    }
    result.summary={styles:faces.length,text_checks:result.checks.length,
      differences:Object.fromEntries(['baseline','ext-only','patched','coherent'].map(v=>[v,result.checks.filter(c=>c.outcomes[v].different_pixels!==0).length])),
      failed_font_responses:result.responses.filter(r=>r.status!==200).length,
      webfont_responses:result.responses.length};
    result.candidate_strategy='Coalesced Latin/common with canonical cmap closure; separate Cyrillic font; entire encoded repertoire retained';
    result.literal_nam_status=result.summary.differences.patched ? 'DIFFERENCES REMAIN' : 'PASS';
    result.status=result.summary.failed_font_responses || result.page_errors.length ? 'ERROR' : result.summary.differences.coherent ? 'REGRESSION FOUND' : 'PASS';
  } catch(e) {result.reason=String(e);if(browser)result.status='ERROR';}
  finally {if(browser)await browser.close();}
  fs.writeFileSync(path.join(out,engine+'.json'),JSON.stringify(result,null,2));
  console.log(JSON.stringify({engine,status:result.status,versions:result.versions,summary:result.summary,reason:result.reason}));
  return result;
}
(async()=>{
  await new Promise(resolve=>server.listen(0,'127.0.0.1',resolve));
  const results=[];
  for(const engine of ['chromium','firefox','webkit']) results.push(await test(engine,args[engine+'-executable']?{executablePath:args[engine+'-executable']}:{}));
  const hashes=Object.fromEntries(fs.readdirSync(out).filter(f=>f.endsWith('.png')).map(f=>[f,crypto.createHash('sha256').update(fs.readFileSync(path.join(out,f))).digest('hex')]));
  fs.writeFileSync(path.join(out,'summary.json'),JSON.stringify({results:results.map(r=>({engine:r.engine,status:r.status,versions:r.versions,summary:r.summary,reason:r.reason})),screenshots:hashes,request_count:requests.length},null,2));
  server.close();
  if(results.some(r=>r.status==='ERROR'||r.status==='REGRESSION FOUND'))process.exitCode=1;
})().catch(e=>{console.error(e);server.close();process.exitCode=2;});
