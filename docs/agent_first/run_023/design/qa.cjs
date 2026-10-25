// Render only the owned static mockup. No application import, IPC or web requests.
const fs=require('fs'),path=require('path'),os=require('os');
const {pathToFileURL}=require('url');
const {chromium}=require('C:/Users/wuxia/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright');
const here=__dirname,out=path.join(here,'screenshots');fs.mkdirSync(out,{recursive:true});
const temp=fs.mkdtempSync(path.join(here,'.render-temp-'));
const results=[],errors=[],external=[];
function check(name,value,detail=null){results.push({name,pass:!!value,detail});if(!value)errors.push(name);}
(async()=>{
 const browser=await chromium.launch({executablePath:'C:/Program Files/Google/Chrome/Application/chrome.exe',headless:true,env:{...process.env,TEMP:temp,TMP:temp}});
 let closed=false;browser.on('disconnected',()=>closed=true);
 try{
  const context=await browser.newContext({viewport:{width:1440,height:1000},deviceScaleFactor:1});
  const page=await context.newPage();
  page.on('pageerror',e=>errors.push(String(e)));
  await context.route('**/*',route=>{if(/^https?:/.test(route.request().url())){external.push(route.request().url());return route.abort();}return route.continue();});
  const base=pathToFileURL(path.join(here,'index.html')).href;
  const scenes=[['01-empty','overview','empty','en'],['02-overview','overview','running','en'],['03-runs','runs','running','en'],['04-classic','classic','running','en'],['05-service','service','running','en'],['06-agent','agent','running','en'],['07-settings','settings','running','en'],['08-disconnected','runs','offline','en'],['09-unknown','runs','unknown','en'],['10-empty-project','overview','new','en'],['11-completed','runs','ended','en'],...['zh-CN','fr-FR','de-DE'].map(l=>['locale-'+l,'overview','running',l])];
  for(const [name,view,scene,lang] of scenes){
   await page.goto(base+`?page=${view}&scene=${scene}&lang=${lang}`);
   check(name+'-render',await page.locator('.window').isVisible());
   check(name+'-no-document-horizontal-overflow',await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));
   const clipped=await page.locator('button').evaluateAll(els=>els.filter(el=>el.scrollWidth>el.clientWidth+2||el.scrollHeight>el.clientHeight+2).map(el=>el.textContent));
   check(name+'-button-fit',clipped.length===0,clipped);
   await page.screenshot({path:path.join(out,name+'.png'),fullPage:true});
  }
  for(const lang of ['en','zh-CN','fr-FR','de-DE']){
   await page.goto(base+`?page=projects&scene=empty&lang=${lang}`);
   await page.locator('[data-action="wizard"]').first().click();
   check(lang+'-wizard-only-abaqus',await page.locator('#projectType option').allTextContents().then(a=>a.length===1&&a[0]==='Abaqus'));
   await page.screenshot({path:path.join(out,'wizard-'+lang+'.png')});
   await page.locator('[data-action="wizardNext"]').click();
   check(lang+'-review-paused',await page.locator('.modal').textContent().then(t=>t.includes('PAUSED')));
   await page.locator('[data-action="createPreview"]').click();
   check(lang+'-create-is-simulation',await page.locator('.toast').textContent().then(t=>t.includes('No Project')));
  }
  await page.goto(base+'?scene=running');
  for(const nav of ['classic','runs','projects','queue','results','agent','service','settings','overview']){
   await page.locator(`nav [data-page="${nav}"]`).click();
   check('navigation-'+nav,await page.locator(`nav [data-page="${nav}"]`).getAttribute('aria-current')==='page');
  }
  await page.locator('nav [data-page="runs"]').click();
  for(const tab of ['identity','events','evidence']){await page.locator(`[data-tab="${tab}"]`).click();check('tab-'+tab,await page.locator(`[data-tab="${tab}"]`).getAttribute('aria-selected')==='true');}
  await page.locator('nav [data-page="overview"]').click();
  const before=await page.evaluate(()=>getComputedStyle(document.documentElement).getPropertyValue('--queue'));
  await page.locator('.divider').focus();await page.keyboard.press('ArrowLeft');
  check('keyboard-resize',before!==await page.evaluate(()=>getComputedStyle(document.documentElement).getPropertyValue('--queue')));
  await page.locator('nav [data-page="classic"]').click();
  check('classic-logs-isolated',!(await page.locator('.logdock').textContent()).includes('run_demo_0042'));
  check('classic-results-no-dat-proof',!(await page.locator('.split').textContent()).includes('DAT / ODB'));
  for(const lang of ['en','zh-CN','fr-FR','de-DE']){
   await page.goto(base+`?page=service&scene=running&lang=${lang}`);
   check(lang+'-service-buttons-fit',await page.locator('.serviceButtons button').evaluateAll(els=>els.every(el=>el.scrollWidth<=el.clientWidth+2 && el.scrollHeight<=el.clientHeight+2)));
  }
  await page.setViewportSize({width:1100,height:820});
  await page.goto(base+'?page=runs&scene=offline&lang=de-DE');
  check('german-compact-no-document-overflow',await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));
  check('german-compact-scroll-available',await page.locator('.content').evaluate(el=>getComputedStyle(el).overflowY==='auto'));
  await page.screenshot({path:path.join(out,'german-1100.png'),fullPage:true});
  await context.close();
 }finally{await browser.close();}
 check('browser-closed',closed);check('no-web-requests',external.length===0,external);
 // Only this invocation's fresh profile/cache directory, after browser closure.
 if(!path.resolve(temp).startsWith(path.resolve(here)+path.sep+'.render-temp-'))throw Error('cleanup boundary');
 fs.rmSync(temp,{recursive:true});
 check('owned-render-temp-removed',!fs.existsSync(temp));
 const report={scope:'Static HTML only; not Tk implementation or service regression',results,errors,external_requests:external,browser_closed:closed};
 fs.writeFileSync(path.join(here,'QA_RESULTS.json'),JSON.stringify(report,null,2));
 console.log(JSON.stringify({checks:results.length,failures:errors,external_requests:external.length,browser_closed:closed}));
 if(errors.length)process.exitCode=1;
})().catch(e=>{console.error(e);process.exitCode=1;});
