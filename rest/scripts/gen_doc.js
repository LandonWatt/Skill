// Build the email-format Word doc from data.json + table.png — matches the Outlook email formatting exactly.
// Usage: node gen_doc.js <data.json> <table.png> <out.docx>
const fs=require("fs");
const { Document, Packer, Paragraph, TextRun, AlignmentType, LevelFormat, ImageRun, PageOrientation } = require("docx");
const data=JSON.parse(fs.readFileSync(process.argv[2],"utf8"));
const img=fs.readFileSync(process.argv[3]);
const out=process.argv[4];
const RL={CARD_DECLINED:"Card Declined / Insufficient Funds",REPEAT_OFFENSE:"Repeat Offense",GUEST_COMPLAINT:"Guest Complaint",OTHER:"Other",VIP:"VIP / Loyalty",AIRLINE_GROUP:"Airlines / Groups",GUEST_WARNED:"Guest Warned",NO_CARD:"No Card on File",VACANT:"Vacant / Checked Out",CHARGEBACK:"Chargeback",CHARGED_LATER:"Charged Later",UNBOOKED:"Unbooked"};
const {asof,since,chargeRate,incRate,capex,financed,windowed,greeting}=data;
function fmtd(s){const a=s.split("-").map(Number);return a[1]+"/"+a[2]+"/"+a[0];}
function mdy(s){s=String(s);return /^\d{4}-\d{2}-\d{2}$/.test(s)?(()=>{const a=s.split("-").map(Number);return a[1]+"/"+a[2]+"/"+a[0];})():s;}
function money(n){return "$"+Number(n).toLocaleString("en-US",{minimumFractionDigits:2,maximumFractionDigits:2});}
function shown(evs){return evs.filter(e=>!(e[3]==="REPEAT_OFFENSE")&&!(e[1]>0&&e[1]>=e[2]));}
function pngSize(b){return {w:b.readUInt32BE(16),h:b.readUInt32BE(20)};}
const ch=[];
const LS={line:276,lineRule:"auto"};             // 115% line spacing
const P=(runs,opt={})=>ch.push(new Paragraph(Object.assign({children:runs,spacing:LS},opt)));
const BLANK=()=>ch.push(new Paragraph({spacing:LS,children:[new TextRun("")]}));
const hdr=t=>[new TextRun({text:t,bold:true,underline:{}})];        // bold + underline section header
const capW=(chargeRate<75)?"below":(chargeRate>75?"above":"at");
const incW=(incRate<0.60)?"below":(incRate>0.60?"above":"at");

P([new TextRun(greeting||"Good afternoon,")]);
BLANK();
P([new TextRun(`Here is an update on the Rest Smoking Sensor Initiative as of ${mdy(asof)}. Please let me know if you have any questions.`)]);
BLANK();
P(hdr("Chosen model Decision:"));
BLANK();
P([new TextRun({text:"Capex:",italics:true,underline:{}})]);
capex.forEach(x=>P([new TextRun({text:x,bold:true})],{numbering:{reference:"capex",level:0}}));
BLANK();
P([new TextRun({text:"Financed:",italics:true,underline:{}})]);
financed.forEach(x=>P([new TextRun({text:x,bold:true})],{numbering:{reference:"fin",level:0}}));
BLANK();
P(hdr("Hotels that are live and charging for smoking/vaping:"));
for(const row of windowed){
  const name=row.name,X=row.X,Y=row.Y,evs=row.events||[];
  P([new TextRun({text:name,bold:true})],{numbering:{reference:"outline",level:0},spacing:{line:276,lineRule:"auto",before:80}});
  P([new TextRun(`Successfully charged ${X} of ${Y} events (since ${mdy(since)}).`)],{numbering:{reference:"outline",level:1}});
  for(const e of shown(evs)){const [d,net,chg,r,c]=e; const cmt=(c&&c.trim())?("“"+c.trim()+"”"):"(no comment recorded)"; let runs;
    if(net>0) runs=[new TextRun(`${fmtd(d)} — Charged ${money(net)} — ${RL[r]||r}: `),new TextRun({text:cmt,italics:true})];
    else if(r) runs=[new TextRun(`${fmtd(d)} — Not charged — ${RL[r]||r}: `),new TextRun({text:cmt,italics:true})];
    else runs=[new TextRun(`${fmtd(d)} — `),new TextRun({text:"Not yet charged (pending)",bold:true})];
    P(runs,{numbering:{reference:"outline",level:2}});}
}
BLANK();
P(hdr("Best Practices:"));
P([new TextRun("A common practice identified is that when there are insufficient funds to complete the smoking charge, property teams attempt to charge lower amounts until a charge goes through. In addition to this practice, we request that hotels also increase their credit card incidental holds to $250. Please let me know if you disagree.")]);
BLANK();
P(hdr("Portfolio Statistics:"));
P([
  new TextRun(`The portfolio’s charge rate is ${chargeRate}%, `),
  new TextRun({text:capW,bold:true,underline:{}}),
  new TextRun(` the 75% target, and the incident rate is ${incRate}% per available room, `),
  new TextRun({text:incW,bold:true,underline:{}}),
  new TextRun(` the 0.60% target.`)
],{numbering:{reference:"stat",level:0}});
// embedded table picture — own landscape page, sized large (10in wide @96dpi = 960px)
const sz=pngSize(img); const W=960, H=Math.round(W*sz.h/sz.w);
const imgCh=[new Paragraph({children:[new ImageRun({type:"png",data:img,transformation:{width:W,height:H},altText:{title:"Email format summary",description:"Rest email-format sheet",name:"EmailFormat"}})]})];

// signature section (portrait)
const sigCh=[];
sigCh.push(new Paragraph({spacing:LS,children:[new TextRun("Best,")]}));
sigCh.push(new Paragraph({children:[new TextRun({text:" ",font:"Segoe UI",size:24})]}));
sigCh.push(new Paragraph({children:[new TextRun({text:"LANDON WATTS",bold:true,font:"Segoe UI",color:"4E6A84",size:24})]}));
const sig=t=>sigCh.push(new Paragraph({children:[new TextRun({text:t,font:"Segoe UI Light",color:"000000",size:22})]}));
sig("Noble Investment Group | Analyst – Asset Management");
sig("2000 Monarch Tower | 3424 Peachtree Road, NE | Atlanta, Georgia 30326");
sig("770.468.2211");
sigCh.push(new Paragraph({children:[new TextRun({text:"landon.watts@nobleinvestment.com | www.nobleinvestment.com",font:"Segoe UI Light",color:"467886",size:22})]}));

const lv=(fmt,txt,ind)=>({level:0,format:fmt,text:txt,alignment:AlignmentType.LEFT,style:{paragraph:{indent:{left:ind,hanging:360}}}});
const doc=new Document({
  styles:{default:{document:{run:{font:"Aptos",size:24}}}},   // body = Aptos 12pt (matches MsoNormal)
  numbering:{config:[
    {reference:"capex",levels:[lv(LevelFormat.DECIMAL,"%1.",360)]},
    {reference:"fin",levels:[lv(LevelFormat.DECIMAL,"%1.",360)]},
    {reference:"stat",levels:[{level:0,format:LevelFormat.BULLET,text:"•",alignment:AlignmentType.LEFT,style:{paragraph:{indent:{left:360,hanging:360}}}}]},
    {reference:"outline",levels:[
      {level:0,format:LevelFormat.DECIMAL,text:"%1.",alignment:AlignmentType.LEFT,style:{paragraph:{indent:{left:360,hanging:360}}}},
      {level:1,format:LevelFormat.LOWER_LETTER,text:"%2.",alignment:AlignmentType.LEFT,style:{paragraph:{indent:{left:720,hanging:360}}}},
      {level:2,format:LevelFormat.BULLET,text:"•",alignment:AlignmentType.LEFT,style:{paragraph:{indent:{left:1080,hanging:360}}}},
    ]},
  ]},
  sections:[
    {properties:{page:{size:{width:12240,height:15840},margin:{top:1440,right:1440,bottom:1440,left:1440}}},children:ch},
    {properties:{page:{size:{orientation:PageOrientation.LANDSCAPE,width:12240,height:15840},margin:{top:720,right:720,bottom:720,left:720}}},children:imgCh},
    {properties:{page:{size:{width:12240,height:15840},margin:{top:1440,right:1440,bottom:1440,left:1440}}},children:sigCh}
  ]
});
Packer.toBuffer(doc).then(b=>{fs.writeFileSync(out,b);console.log("saved "+out);});
