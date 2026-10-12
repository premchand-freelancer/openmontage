// Exercise the installed renderer/encoder without relying on past project assets.
const fs=require('fs');
const path=require('path');
const {createRequire}=require('module');
const {execFileSync}=require('child_process');
async function run(){
 const engine=path.resolve(process.argv[2]);
 const browser=process.argv[3];
 const composer=path.join(engine,'remotion-composer');
 const localRequire=createRequire(path.join(composer,'package.json'));
 const {bundle}=localRequire('@remotion/bundler');
 const {selectComposition,renderMedia}=localRequire('@remotion/renderer');
 fs.mkdirSync(path.join(engine,'projects'),{recursive:true});
 const directory=fs.mkdtempSync(path.join(engine,'projects','runtime-smoke-'));
 try{
  const entry=path.join(directory,'index.tsx');
  fs.writeFileSync(entry,`import React from 'react';import {registerRoot,Composition,AbsoluteFill,useCurrentFrame} from 'remotion';const Check=()=>{const f=useCurrentFrame();return <AbsoluteFill style={{background:'#07141e',justifyContent:'center',alignItems:'center',color:'#38c7ed',fontSize:26}}><div style={{transform:'translateX('+f*2+'px)'}}>OpenMontage</div></AbsoluteFill>};registerRoot(()=> <Composition id="RuntimeSmoke" component={Check} width={256} height={384} fps={30} durationInFrames={9}/>);`);
  const serveUrl=await bundle({entryPoint:entry,publicDir:directory,webpackOverride:c=>({...c,resolve:{...c.resolve,modules:[path.join(composer,'node_modules'),...(c.resolve.modules||[])]}})});
  const composition=await selectComposition({serveUrl,id:'RuntimeSmoke',browserExecutable:browser});
  const output=path.join(directory,'smoke.mp4');
  await renderMedia({serveUrl,composition,outputLocation:output,codec:'h264',pixelFormat:'yuv420p',imageFormat:'jpeg',browserExecutable:browser,concurrency:1});
  const probe=JSON.parse(execFileSync('ffprobe',['-v','error','-show_streams','-of','json',output],{encoding:'utf8'}));
  const video=probe.streams.find(s=>s.codec_type==='video');
  if(video.width!==256||video.height!==384||video.nb_frames!=='9'||video.codec_name!=='h264')throw Error('Incorrect smoke export');
  execFileSync('ffmpeg',['-nostdin','-v','error','-xerror','-i',output,'-f','null','-']);
  console.log(JSON.stringify({status:'passed',codec:'h264',resolution:'256x384',frames:9,full_decode_passed:true}));
 }finally{fs.rmSync(directory,{recursive:true,force:true});}
}
run().catch(e=>{console.error(e.message);process.exit(1)});
