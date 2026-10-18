// Real built proxy and upload route in platform mode; no platform backend or stored data.
const fs=require('node:fs'),path=require('node:path'),http=require('node:http');
const {spawn}=require('node:child_process');
const root=path.resolve(__dirname,'..'),out=path.resolve(process.argv[2]||'/tmp/doclens-main-mode-review');fs.mkdirSync(out,{recursive:true});let child;
(async()=>{
 const socket=http.createServer();await new Promise(r=>socket.listen(0,'127.0.0.1',r));const port=socket.address().port;await new Promise(r=>socket.close(r));const origin=`http://127.0.0.1:${port}`;
 const log=fs.openSync(path.join(out,'next.log'),'w');child=spawn('node',['node_modules/next/dist/bin/next','start','--hostname','127.0.0.1','--port',String(port)],{cwd:path.join(root,'frontend'),env:{...process.env,DOCLENS_PLATFORM_ENABLED:'1',PLATFORM_PUBLIC_ORIGIN:origin,NEXT_TELEMETRY_DISABLED:'1'},stdio:['ignore',log,log]});
 let ready=false;for(let i=0;i<150;i++){if(child.exitCode!==null)throw Error('Next exited');try{if((await fetch(origin+'/workspaces')).status===200){ready=true;break;}}catch{}await new Promise(r=>setTimeout(r,100));}if(!ready)throw Error('Readiness timeout');
 const results=[];
 for(const [method,url,expected] of [['GET','/dashboard',404],['GET','/monitoring',404],['POST','/api/ask',404],['POST','/api/auth/login',404],['POST','/api/documents/process',404],['GET','/workspaces',200]]){const r=await fetch(origin+url,{method,redirect:'manual'});results.push({method,url,status:r.status,expected});if(r.status!==expected)throw Error(JSON.stringify(results));}
 const home=await fetch(origin,{redirect:'manual'});if(![307,308].includes(home.status)||new URL(home.headers.get('location'),origin).href!==origin+'/workspaces')throw Error(JSON.stringify({problem:'Platform landing redirect changed',status:home.status,location:home.headers.get('location'),expected:origin+'/workspaces'}));results.push({url:'/',status:home.status,location:home.headers.get('location')});
 fs.writeFileSync(path.join(out,'results.json'),JSON.stringify({mode:'platform',checks:results,backend:'Not started; only existing Next isolation boundaries tested'},null,2)+'\n');console.log(JSON.stringify(results));
})().catch(e=>{console.error(e);process.exitCode=1}).finally(()=>{if(child)child.kill('SIGTERM')});
