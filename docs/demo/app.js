"use strict";
const $ = id => document.getElementById(id);
const NS = "http://www.w3.org/2000/svg";
const descriptions = {
  relaxation: ["Energy relaxation", "An initially excited qubit returns to its ground state. The analytic population decays as exp(−t/T₁)."],
  dephasing: ["Loss of phase coherence", "A prepared X superposition loses contrast. Both relaxation and pure dephasing contribute to the transverse decay time T₂."],
  rabi: ["Driven Rabi oscillations", "A continuous drive transfers population between the two levels. Relaxation and dephasing damp the motion; detuning changes its amplitude and frequency."],
  ramsey: ["Ramsey interference", "An ideal preparation pulse creates a superposition. Free evolution accumulates phase before ideal X readout. Each trajectory has a fixed sampled detuning."],
  echo: ["Hahn echo", "An ideal π-X pulse halfway through each delay reverses static phase accumulation. Markovian dephasing remains, so echo restores only the reversible part."],
};
let result, selected = 0;
let downloadUrls = [];
function downloads(r, imported) {
  downloadUrls.forEach(url => URL.revokeObjectURL(url)); downloadUrls = [];
  function setLink(selector, text, type) {
    const url = URL.createObjectURL(new Blob([text], {type})); downloadUrls.push(url);
    document.querySelectorAll(selector).forEach(link => {link.href = url;});
  }
  setLink('a[download="results.json"]', JSON.stringify(r, null, 2), "application/json");
  const rows = ["experiment_index,kind,time_us,signal,reference,synthetic_measurement,wilson_low95,wilson_high95"];
  r.experiments.forEach((e,i) => e.time_us.forEach((t,j) => rows.push([i,e.config.kind,t,e.signal[j],e.reference?.[j]??"",e.measurement?.value[j]??"",e.measurement?.low95[j]??"",e.measurement?.high95[j]??""].join(","))));
  setLink('a[download="experiments.csv"]', rows.join("\n")+"\n", "text/csv");
  if(r.sweep) {
    const s=r.sweep, rows=["drive_mhz,detuning_mhz,excited_population"];
    s.excited_population.forEach((row,i)=>row.forEach((v,j)=>rows.push([s.drive_mhz[i],s.detuning_mhz[j],v].join(","))));
    setLink('a[download="sweep.csv"]', rows.join("\n")+"\n", "text/csv");
  }
  document.querySelectorAll('a[data-bundled]').forEach(a=>{a.hidden=imported;});
}
function svg(parent, tag, attrs = {}, text = "") {
  const element = document.createElementNS(NS, tag);
  Object.entries(attrs).forEach(([key, value]) => element.setAttribute(key, value));
  element.textContent = text; parent.appendChild(element); return element;
}
function format(x) { return x === null ? "off" : Number(x).toPrecision(4); }
function finiteArray(a, n) { return Array.isArray(a) && a.length === n && a.every(Number.isFinite); }
function validate(r) {
  if (!r || r.schema_version !== 1 || r.simulation_only !== true || !r.provenance || !Array.isArray(r.experiments) || r.experiments.length < 1 || r.experiments.length > 30) throw Error("Expected a QuantumNoiseLab schema version 1 simulation report.");
  for (const e of r.experiments) {
    const n = e.time_us?.length;
    if (!e.config || !descriptions[e.config.kind] || !e.diagnostics || !Number.isInteger(n) || n < 2 || n > 10001 || !finiteArray(e.time_us, n) || !finiteArray(e.signal, n) || !e.bloch || !["x", "y", "z"].every(k => finiteArray(e.bloch[k], n)) || (e.reference !== null && !finiteArray(e.reference, n))) throw Error("Invalid experiment arrays or configuration.");
    if (e.time_us[0] !== 0 || e.time_us.some((t, i) => i && t <= e.time_us[i-1])) throw Error("Time samples must increase from zero.");
    if (e.measurement && !["value", "low95", "high95"].every(k => finiteArray(e.measurement[k], n))) throw Error("Invalid measurement arrays.");
  }
  if (r.sweep) {
    const s = r.sweep, nx = s.detuning_mhz?.length, ny = s.drive_mhz?.length;
    if (!Number.isInteger(nx) || !Number.isInteger(ny) || nx < 2 || ny < 2 || nx > 101 || ny > 101 || !finiteArray(s.detuning_mhz, nx) || !finiteArray(s.drive_mhz, ny) || !Array.isArray(s.excited_population) || s.excited_population.length !== ny || !s.excited_population.every(row => finiteArray(row, nx)) || !s.config) throw Error("Invalid sweep grid.");
  }
}
function table(target, headers, rows) {
  target.replaceChildren();
  const head = target.createTHead().insertRow();
  headers.forEach(h => { const th = document.createElement("th"); th.scope = "col"; th.textContent = h; head.appendChild(th); });
  const body = target.createTBody();
  rows.forEach(row => { const tr = body.insertRow(); row.forEach(value => { tr.insertCell().textContent = value; }); });
}
function chart() {
  const e = result.experiments[selected], metric = $("metric").value;
  const signal = metric === "signal" ? e.signal : e.bloch[metric];
  const graph = $("chart"); graph.replaceChildren();
  svg(graph, "title", {}, `${e.config.kind}: ${metric}, computed time series`);
  svg(graph, "desc", {}, "Numerical values are available in the sample slider and data table.");
  const left=62, top=20, width=733, height=264, ymin=metric==="signal" && ["rabi","relaxation"].includes(e.config.kind) ? 0 : -1, ymax=1;
  const x=t=>left+t/e.time_us.at(-1)*width, y=v=>top+(ymax-v)/(ymax-ymin)*height;
  for(let i=0;i<=4;i++) {
    const v=ymin+(ymax-ymin)*i/4, t=e.time_us.at(-1)*i/4;
    svg(graph,"line",{x1:left,x2:left+width,y1:y(v),y2:y(v),stroke:"#e0e6e1"});
    svg(graph,"text",{x:left-12,y:y(v)+4,"text-anchor":"end"},v.toFixed(2));
    svg(graph,"text",{x:x(t),y:top+height+23,"text-anchor":"middle"},t.toFixed(1));
  }
  svg(graph,"text",{x:430,y:333,"text-anchor":"middle"},"Delay / evolution time (µs)");
  const path=values=>values.map((v,i)=>`${i?"L":"M"}${x(e.time_us[i]).toFixed(2)},${y(v).toFixed(2)}`).join(" ");
  if(metric==="signal" && e.measurement && $("shots").checked) {
    const m=e.measurement;
    const points=[...m.high95.map((v,i)=>`${x(e.time_us[i])},${y(v)}`),...m.low95.map((v,i)=>`${x(e.time_us[i])},${y(v)}`).reverse()].join(" ");
    svg(graph,"polygon",{points,fill:"#cfe5e2",opacity:".65"});
    m.value.forEach((v,i)=>svg(graph,"circle",{cx:x(e.time_us[i]),cy:y(v),r:2,fill:"#517e80"}));
  }
  svg(graph,"path",{d:path(signal),stroke:"#007d82","stroke-width":2.5,fill:"none"});
  if(metric==="signal" && e.reference && $("reference").checked) svg(graph,"path",{d:path(e.reference),stroke:"#a9631d","stroke-width":1.8,"stroke-dasharray":"6 5",fill:"none"});
  const index=Math.min(Number($("sample").value),signal.length-1);
  svg(graph,"line",{x1:x(e.time_us[index]),x2:x(e.time_us[index]),y1:top,y2:top+height,stroke:"#536c77","stroke-dasharray":"3 4"});
  svg(graph,"circle",{cx:x(e.time_us[index]),cy:y(signal[index]),r:4,fill:"#162c38",stroke:"white","stroke-width":2});
  $("sample-value").textContent=`t = ${format(e.time_us[index])} µs · ${metric} = ${format(signal[index])}`;
  $("reference").disabled = metric !== "signal" || !e.reference;
  $("shots").disabled = metric !== "signal" || !e.measurement;
}
function renderExperiment() {
  const e=result.experiments[selected], c=e.config;
  $("experiment-number").textContent=`EXPERIMENT ${String(selected+1).padStart(2,"0")} / ${String(result.experiments.length).padStart(2,"0")}`;
  $("experiment-title").textContent=descriptions[c.kind][0];
  $("description").textContent=descriptions[c.kind][1];
  $("observable").textContent=e.observable;
  $("metrics").replaceChildren();
  [["T₁ / µs",format(c.t1_us)],["T₂ / µs",format(e.t2_us)],["Detuning / MHz",format(["relaxation","dephasing"].includes(c.kind)?0:c.detuning_mhz)],["Shots / sample",c.shots]].forEach(([name,value])=>{
    const card=document.createElement("div");card.className="metric";
    const b=document.createElement("b"),span=document.createElement("span");b.textContent=value;span.textContent=name;card.append(b,span);$("metrics").appendChild(card);
  });
  $("sample").max=e.time_us.length-1;$("sample").value=0;
  $("config").textContent=JSON.stringify(c,null,2);
  $("diagnostics").replaceChildren();
  Object.entries(e.diagnostics).forEach(([name,value])=>{const row=document.createElement("div");row.className="diagnostic";const label=document.createElement("span"),code=document.createElement("code");label.textContent=name.replaceAll("_"," ");code.textContent=value===null?"not applicable":format(value);row.append(label,code);$("diagnostics").appendChild(row);});
  table($("data-table"),["Time (µs)","Signal","Reference","Shots","95% low","95% high"],e.time_us.map((t,i)=>[format(t),format(e.signal[i]),e.reference?format(e.reference[i]):"—",...(e.measurement?["value","low95","high95"].map(k=>format(e.measurement[k][i])):["—","—","—"])]));
  document.querySelectorAll("#experiments button").forEach((b,i)=>b.setAttribute("aria-current",i===selected?"true":"false"));
  chart();
}
function heatmap() {
  const s=result.sweep;$("sweep-panel").hidden=!s;if(!s)return;
  const g=$("heatmap");g.replaceChildren();
  const nx=s.detuning_mhz.length,ny=s.drive_mhz.length,w=560/nx,h=260/ny;
  s.excited_population.forEach((row,i)=>row.forEach((v,j)=>{const clamped=Math.max(0,Math.min(1,v));const rect=svg(g,"rect",{x:65+j*w,y:20+(ny-1-i)*h,width:w+.2,height:h+.2,fill:`rgb(${Math.round(239-220*clamped)},${Math.round(246-116*clamped)},${Math.round(222-91*clamped)})`});svg(rect,"title",{},`Drive ${format(s.drive_mhz[i])} MHz, detuning ${format(s.detuning_mhz[j])} MHz: ${format(v)}`);}));
  for(let k=0;k<=4;k++){svg(g,"text",{x:65+560*k/4,y:301,"text-anchor":"middle"},format(s.detuning_mhz[0]+(s.detuning_mhz.at(-1)-s.detuning_mhz[0])*k/4));svg(g,"text",{x:57,y:284-260*k/4,"text-anchor":"end"},format(s.drive_mhz[0]+(s.drive_mhz.at(-1)-s.drive_mhz[0])*k/4));}
  svg(g,"text",{x:345,y:330,"text-anchor":"middle"},"Detuning (MHz)");
  svg(g,"text",{transform:"translate(14 150) rotate(-90)","text-anchor":"middle"},"Drive (MHz)");
  svg(g,"text",{x:350,y:350,"text-anchor":"middle"},"Light → dark: excited population 0 → 1");
  $("sweep-caption").textContent=`${nx*ny} trajectories · evolution ${s.config.duration_us??40} µs · no synthetic shots`;
  table($("sweep-table"),["Drive (MHz)",...s.detuning_mhz.map(x=>`Δ ${format(x)}`)],s.excited_population.map((row,i)=>[format(s.drive_mhz[i]),...row.map(format)]));
}
function load(r, imported=false) {
  validate(r);result=r;selected=0;$("error").hidden=true;
  $("run-summary").textContent=`${r.experiments.length} experiments · ${Number(r.provenance.runtime_seconds).toFixed(2)} s · QuTiP ${r.provenance.dependencies?.qutip??"unknown"}`;
  $("provenance").textContent=JSON.stringify(r.provenance,null,2);
  $("experiments").replaceChildren();
  r.experiments.forEach((e,i)=>{const button=document.createElement("button"),label=document.createElement("span"),small=document.createElement("small");label.textContent=descriptions[e.config.kind][0];small.textContent=`${e.time_us.length} samples · ${e.config.duration_us} µs`;button.append(label,small);button.addEventListener("click",()=>{selected=i;renderExperiment();});$("experiments").appendChild(button);});
  renderExperiment();heatmap();downloads(r, imported);
}
["metric","reference","shots"].forEach(id=>$(id).addEventListener("change",chart));
$("sample").addEventListener("input",chart);
$("file").addEventListener("change",async event=>{try{const file=event.target.files[0];if(!file)return;if(file.size>20*1024*1024)throw Error("Choose a report smaller than 20 MB.");load(JSON.parse(await file.text()),true);}catch(error){$("error").textContent=error.message;$("error").hidden=false;}});
try{load(window.QUANTUM_NOISE_RESULTS);}catch(error){$("error").textContent=`Cannot load report: ${error.message}`;$("error").hidden=false;}
