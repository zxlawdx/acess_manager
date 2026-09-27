/* Contract: Vela classic management shim + native ES-module inventory rendering. */
"use strict";
const assert = require("node:assert/strict");
const fs = require("node:fs");

const source = fs.readFileSync(
    "apps/zte_manager/static/js/management/inventory_view.js", "utf8"
);
const legacy = fs.readFileSync(
    "apps/zte_manager/static/js/management.js", "utf8"
);
const html = fs.readFileSync(
    "apps/zte_manager/templates/index.html", "utf8"
);
assert.ok(source.includes("export function createInventoryView(options)"));
assert.ok(source.includes("new AbortController()"));
assert.ok(source.includes("body.replaceChildren(fragment)"));
assert.ok(!source.includes(".innerHTML"), "Inventory must never use mass HTML injection");
assert.ok(legacy.includes("window.managementInventoryView?.getCheckedIds()"));
assert.ok(!legacy.includes("navigator.userAgent"),
    "Management clipboard must use the shared Python-host capabilities");
assert.ok(html.includes('type="module" src="{{ static(\'zte_manager/js/management/inventory_view.js\') }}"'));

class Node {
    constructor(tag, doc) {
        this.tag = tag.toUpperCase();
        this.ownerDocument = doc;
        this.children = [];
        this.parentNode = null;
        this.dataset = {};
        this.attributes = {};
        this.listeners = {};
        this.listenerRegistrations = 0;
        this.textContent = "";
        this.value = "";
        this.checked = false;
        const classes = new Set();
        this.classList = {
            add(name) { classes.add(name); },
            contains(name) { return classes.has(name); }
        };
    }
    append(...nodes) {
        for (const node of nodes) {
            const items = node.tag === "#DOCUMENT-FRAGMENT"
                ? [...node.children] : [node];
            for (const item of items) {
                item.parentNode = this;
                this.children.push(item);
            }
            if (node.tag === "#DOCUMENT-FRAGMENT") node.children = [];
        }
    }
    replaceChildren(node) {
        for (const old of this.children) old.parentNode = null;
        this.children = [];
        if (node) this.append(node);
    }
    setAttribute(key,value) {this.attributes[key]=value;}
    contains(node) {
        for (let current=node;current;current=current.parentNode) {
            if (current===this) return true;
        }
        return false;
    }
    closest(selector) {
        for (let node=this;node;node=node.parentNode) {
            if (selector==="input.management-device-check" &&
                node.tag==="INPUT" &&
                node.className==="management-device-check") return node;
            if (selector==="tr[data-device-id]" && node.tag==="TR" &&
                node.dataset.deviceId) return node;
        }
        return null;
    }
    addEventListener(type,handler,options={}) {
        this.listeners[type] = handler;
        this.listenerRegistrations++;
        options.signal?.addEventListener("abort",()=>delete this.listeners[type],
            {once:true});
    }
    emit(type,target) {this.listeners[type]?.({target});}
}
class Doc {
    createElement(tag) { return new Node(tag,this); }
    createDocumentFragment() {return new Node("#document-fragment",this);}
}
function byTag(node,tag) {
    if (node.tag===tag.toUpperCase()) return node;
    for (const child of node.children) {
        const match=byTag(child,tag);
        if(match) return match;
    }
    return null;
}
function textOf(node) {
    return node.textContent + node.children.map(textOf).join(" ");
}

(async function main(){
    // Data URL import exercises a real ES Module without adding npm/jsdom deps.
    const url="data:text/javascript;base64,"+
        Buffer.from(source,"utf8").toString("base64");
    const {createInventoryView}=await import(url);
    const doc=new Doc();
    const body=doc.createElement("tbody");
    const selected=[];
    const view=createInventoryView({
        body, onSelect:id=>selected.push(id),
        relativeTime:()=> "1 min"
    });
    const devices=[
        {id:1,model:"F670L",customer_name:"<script>alert(1)</script>",
         firmware:"FW-1",serial:"SERIAL1",status:"online"},
        {id:2,model:"F6600P",customer_name:"Bravo",
         firmware:"FW-2",status:"offline"}
    ];
    view.render({devices,selectedDeviceId:2});
    assert.equal(body.children.length,2);
    assert.equal(body.listenerRegistrations,2,
        "Delegated listeners must be registered only once");
    assert.equal(body.children[1].classList.contains("selected"),true);
    assert.ok(textOf(body.children[0]).includes("<script>alert(1)</script>"));
    assert.ok(textOf(body.children[0]).includes("FW FW-1"));
    const firstCheckbox=byTag(body.children[0],"input");
    firstCheckbox.checked=true;
    body.emit("change",firstCheckbox);
    assert.deepEqual(view.getCheckedIds(),[1]);

    view.render({devices,query:"Bravo"});
    assert.equal(body.children.length,1);
    assert.equal(body.children[0].dataset.deviceId,"2");
    assert.deepEqual(view.getCheckedIds(),[1],
        "Filtered-out checked devices must remain selected");

    view.render({devices,query:""});
    assert.equal(byTag(body.children[0],"input").checked,true);
    body.emit("click",byTag(body.children[0],"strong"));
    assert.deepEqual(selected,[1]);
    assert.equal(body.listenerRegistrations,2,
        "Rerenders must never register row listeners");

    view.render({devices:devices.slice(1),query:""});
    assert.deepEqual(view.getCheckedIds(),[],
        "Missing devices must be pruned from persistent selection");
    view.dispose();
    assert.equal(Object.keys(body.listeners).length,0,
        "Dispose must abort delegated tbody listeners");
    console.log("Inventory ES module: DOM-safe rendering, selection, delegation, cleanup.");
})().catch(err=>{console.error(err);process.exitCode=1});
