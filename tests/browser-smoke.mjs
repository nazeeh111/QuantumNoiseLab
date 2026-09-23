// Optional real-browser check. Start isolated Chrome with remote debugging and
// pass its localhost port and the absolute generated index.html path.
import fs from "node:fs";
import assert from "node:assert/strict";
import {pathToFileURL} from "node:url";

const [port, report, screenshots = "/tmp"] = process.argv.slice(2);
if (!port || !report) throw Error("Usage: node tests/browser-smoke.mjs PORT /absolute/report/index.html [screenshot-directory]");
const tabs = await (await fetch(`http://127.0.0.1:${port}/json`)).json();
const page = tabs.find(t => t.type === "page");
const ws = new WebSocket(page.webSocketDebuggerUrl);
await new Promise((resolve,reject) => {ws.onopen=resolve;ws.onerror=reject;});
let next = 0;
const pending = new Map(), errors=[];
ws.onmessage = event => {
  const message=JSON.parse(event.data);
  if(message.method==="Runtime.exceptionThrown") errors.push(message.params.exceptionDetails);
  const p=pending.get(message.id);
  if(p) {pending.delete(message.id);message.error?p.reject(Error(JSON.stringify(message.error))):p.resolve(message.result);}
};
function call(method,params={}) {return new Promise((resolve,reject)=>{const id=++next;pending.set(id,{resolve,reject});ws.send(JSON.stringify({id,method,params}));});}
async function evaluate(expression) {const r=await call("Runtime.evaluate",{expression,returnByValue:true,awaitPromise:true});if(r.exceptionDetails)throw Error(JSON.stringify(r.exceptionDetails));return r.result.value;}
try {
  await call("Runtime.enable");
  await call("Emulation.setDeviceMetricsOverride",{width:1440,height:1100,deviceScaleFactor:1,mobile:false});
  await call("Page.navigate",{url:pathToFileURL(report).href});
  for(let i=0;i<50;i++){if(await evaluate('document.querySelectorAll("#experiments button").length===5'))break;await new Promise(r=>setTimeout(r,100));}
  assert.equal(await evaluate('document.querySelectorAll("#experiments button").length'),5);
  assert.equal(await evaluate('document.querySelector("#error").hidden'),true);
  assert.equal(await evaluate('document.querySelectorAll("#chart path").length'),2);
  await evaluate('document.querySelectorAll("#experiments button")[4].click()');
  assert.equal(await evaluate('document.querySelector("#experiment-title").textContent'),"Hahn echo");
  await evaluate('document.querySelector("#metric").value="y";document.querySelector("#metric").dispatchEvent(new Event("change"))');
  assert.equal(await evaluate('document.querySelector("#reference").disabled'),true);
  await evaluate('document.querySelector("#sample").value=17;document.querySelector("#sample").dispatchEvent(new Event("input"))');
  assert.match(await evaluate('document.querySelector("#sample-value").textContent'),/y =/);
  await evaluate('document.querySelector("#metric").value="signal";document.querySelector("#metric").dispatchEvent(new Event("change"))');
  const png=await call("Page.captureScreenshot",{format:"png"});fs.writeFileSync(`${screenshots}/quantum-desktop.png`,Buffer.from(png.data,"base64"));
  await call("Emulation.setDeviceMetricsOverride",{width:390,height:844,deviceScaleFactor:1,mobile:true});
  assert.equal(await evaluate('document.documentElement.scrollWidth <= window.innerWidth'),true);
  const mobile=await call("Page.captureScreenshot",{format:"png"});fs.writeFileSync(`${screenshots}/quantum-mobile.png`,Buffer.from(mobile.data,"base64"));
  await evaluate('document.querySelector("#file").files = (()=>{const d=new DataTransfer();d.items.add(new File(["{}"],"bad.json",{type:"application/json"}));return d.files})();document.querySelector("#file").dispatchEvent(new Event("change"))');
  await new Promise(r=>setTimeout(r,100));
  assert.equal(await evaluate('document.querySelector("#error").hidden'),false);
  await evaluate('window.testReport=structuredClone(window.QUANTUM_NOISE_RESULTS);window.testReport.provenance.runtime_seconds=123.45;document.querySelector("#file").files=(()=>{const d=new DataTransfer();d.items.add(new File([JSON.stringify(window.testReport)],"custom.json",{type:"application/json"}));return d.files})();document.querySelector("#file").dispatchEvent(new Event("change"))');
  await new Promise(r=>setTimeout(r,100));
  assert.equal(await evaluate('document.querySelector("#error").hidden'),true);
  assert.equal(await evaluate('(async()=>{const d=await(await fetch(document.querySelector("a[download=\\"results.json\\"]").href)).json();return d.provenance.runtime_seconds;})()'),123.45);
  assert.equal(await evaluate('document.querySelector("a[data-bundled]").hidden'),true);
  assert.equal(errors.length,0,JSON.stringify(errors));
  console.log("PASS: five experiments, overlays, Bloch selection, sample inspection, mobile width, invalid/valid JSON import, current-run download, no browser exceptions");
} finally {ws.close();}
