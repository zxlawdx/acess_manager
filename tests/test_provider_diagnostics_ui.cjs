"use strict";
const test=require("node:test");
const assert=require("node:assert/strict");
const fs=require("node:fs");
const vm=require("node:vm");

const root="apps/zte_manager/";
const app=fs.readFileSync(root+"static/js/features/provider_diagnostics.js","utf8");
const adaptive=fs.readFileSync(root+"static/js/adaptive_firmware.js","utf8");
const support=fs.readFileSync(root+"static/js/support_diagnostics.js","utf8");
const html=fs.readFileSync(root+"templates/index.html","utf8");

function fake(tag="div"){
    const listeners={};
    const element={
        tagName:tag.toUpperCase(),className:"",children:[],
        textContent:"",value:"",checked:false,
        dataset:{},disabled:false,attributes:{},style:{},
        classList:{add(){}},
        setAttribute(name,value){this.attributes[name]=value;},
        addEventListener(name,fn){listeners[name]=fn;},
        append(...nodes){this.children.push(...nodes);},
        appendChild(node){this.children.push(node);return node;},
        replaceChildren(...nodes){this.children=[...nodes];},
        listeners
    };
    return element;
}
const content=(node)=>[node.textContent,...(node.children||[]).map(content)].join(" ");

test("support page includes only real tests and component assets",()=>{
    for(const id of [
        "providerDiagnosticPresets","providerWorkstationRun",
        "providerWorkstationResult","providerPresetStatus",
        "supportDiagnosticForm","supportAutoOptimizeWifi"
    ])assert.ok(html.includes('id="'+id+'"'),id);
    assert.match(html,/features\/provider_diagnostics\.js/);
    assert.match(html,/css\/components\/provider_diagnostics\.css/);
    assert.doesNotMatch(support,/\{ status: "GET confirmado" \}/);
    assert.match(support,/probe_only: true/);
    assert.match(support,/renderRemediationAudit/);
});

test("a preset fills existing form and refuses to silently enable Wi-Fi writes",()=>{
    const elements=Object.fromEntries([
        "supportDiagnosticMode","supportIncludeSpeedtest",
        "supportIncludeTraceroute","supportAutoOptimizeWifi",
        "providerPresetStatus"
    ].map(id=>[id,fake()]));
    const buttons=["no_internet","low_speed","drops","wifi","realtime"].map(key=>{
        const button=fake("button");button.dataset.providerPreset=key;
        return button;
    });
    const doc={
        readyState:"loading",addEventListener(){},
        getElementById:id=>elements[id],
        querySelectorAll:()=>buttons,
        createElement:fake
    };
    const win={};
    vm.runInNewContext(app,{document:doc,window:win});
    const api=win.ProviderDiagnostics;
    assert.ok(api.applyPreset("low_speed"));
    assert.equal(elements.supportDiagnosticMode.value,"low_speed");
    assert.equal(elements.supportIncludeSpeedtest.checked,true);
    assert.equal(elements.supportAutoOptimizeWifi.checked,false);
    assert.equal(buttons[1].attributes["aria-pressed"],"true");
    assert.ok(api.applyPreset("wifi"));
    assert.equal(elements.supportDiagnosticMode.value,"wifi");
    assert.equal(elements.supportIncludeTraceroute.checked,false);
    assert.equal(elements.supportAutoOptimizeWifi.checked,false);
    assert.equal(api.applyPreset("unknown"),false);
});
test("PC report exposes actual measurements with source separation",()=>{
    const doc={readyState:"loading",addEventListener(){},
        createElement:fake};
    const win={};
    vm.runInNewContext(app,{document:doc,window:win});
    const target=fake();
    win.ProviderDiagnostics.renderWorkstation({
        source:"technician_workstation",
        dns:{ok:true,duration_ms:42},
        tcp:{ok:true,attempts:3,successful:2,
            mean_connect_ms:12,variation_ms:3.4},
    },target);
    const text=content(target);
    assert.match(text,/2 de 3/);
    assert.match(text,/42\.0 ms/);
    assert.match(text,/PC do técnico/);
    assert.match(text,/não mede perda de pacotes ICMP/);
    const rejected=fake();
    win.ProviderDiagnostics.renderWorkstation({source:"router"},rejected);
    assert.match(rejected.textContent,/origem/);
});
test("firmware probe is summary only, not a wall of mock GET cards",()=>{
    const doc={readyState:"loading",addEventListener(){},
        createElement:fake};
    const w={};
    vm.runInNewContext(adaptive,{document:doc,window:w});
    const mount=fake();
    w.renderAdaptiveDiagnostic({model:"F6600P",probe_only:true,sections:{
        wifi_advanced:{available:true,data:null},
        wifi_neighbor_scan:{available:true,data:null},
        dhcp_basic:{available:false,reason:"read_failed"}
    }},mount);
    assert.equal(mount.children.length,1);
    assert.equal(mount.children[0].className,"adaptive-probe-result");
    const text=content(mount);
    assert.match(text,/2 de 3 funcionalidades responderam/);
    assert.doesNotMatch(text,/GET|think_lua|wifi_advanced/);
});

test("ONT indicators compute loss from real success/failure counters",()=>{
    const begin=support.indexOf("function renderNetworkIndicators(result) {");
    const end=support.indexOf("function renderAffectedClient(result) {",begin);
    assert.ok(begin>=0&&end>begin);
    const factory=new Function("metric","supportEscape",
        support.slice(begin,end)+";return renderNetworkIndicators;");
    const render=factory(
        (name,value)=>"<p>"+name+": "+String(value)+"</p>",
        value=>String(value).replace(/</g,"&lt;")
    );
    const report={sections:{
        optical:{registration_status:"O5",rx_power_dbm:-19.5},
        wan:[{status:"Up"},{status:"Down"}],
        lan_ports:[{status:"Up"}],
        ping:{medio_ms:"18",sucesso:"3",falha:"1"},
        dns_health:{lookup:{success:true}},
        traceroute:{hops:7}
    }};
    const html=render(report);
    assert.match(html,/25\.0%/);
    assert.match(html,/18 ms/);
    assert.match(html,/1 de 2/);
    assert.match(html,/Resolveu/);
    assert.match(html,/7 saltos/);
    assert.match(html,/não descreve necessariamente a conexão/);
    const incomplete=render({sections:{ping:{medio_ms:"18"}}});
    assert.match(incomplete,/Não medido/);
});
test("Wi-Fi remediation distinguishes proof from a merely accepted command",()=>{
    const begin=support.indexOf("function renderRemediationAudit(result) {");
    const end=support.indexOf("function renderNetworkIndicators(result) {",begin);
    assert.ok(begin>=0&&end>begin);
    const fn=new Function("supportDiagnosticState","supportEscape",
        support.slice(begin,end)+";return renderRemediationAudit;")(
        {lastConfig:{auto_optimize_wifi:true}},value=>String(value)
    );
    assert.match(fn({remediations:[]}),/Nenhuma mudança automática/);
    const content=fn({remediations:[
        {band:"2.4GHz",action:{type:"wifi_channel",channel:11},
            result:{success:true,audit_outcome:"accepted"}},
        {band:"5GHz",action:{type:"wifi_auto_channel"},
            result:{success:true,audit_outcome:"verified"}}
    ]});
    assert.match(content,/aguarda confirmação/);
    assert.match(content,/confirmada pela releitura/);
    assert.match(content,/canal 11/);
});

test("full diagnosis never prints raw router exceptions or paths to a technician",()=>{
    const start=support.indexOf("function renderDiagnosticErrors(result) {");
    const end=support.indexOf("function bindRecommendationActions(root)",start);
    assert.ok(start>=0&&end>start);
    const render=new Function("supportEscape",
        support.slice(start,end)+";return renderDiagnosticErrors;")(value=>String(value));
    const report=render({errors:{
        wifi_environment:"GET /api/router/?token=SECRET; traceback",
        "rule:channel_unknown":"POST /private user admin"
    }});
    assert.match(report,/Interferência Wi-Fi/);
    assert.match(report,/não/);
    assert.doesNotMatch(report,/GET|POST|api\/|token|SECRET|private|traceback/);
});
