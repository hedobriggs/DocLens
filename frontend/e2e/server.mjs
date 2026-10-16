import { createServer } from 'node:http';
import { spawn } from 'node:child_process';
// Controlled upstream exercises the real production Next.js route, not a fetch mock.
const backend = createServer((req, res) => {
  let body = '';
  req.on('data', data => body += data.toString());
  req.on('end', () => {
    if (body.includes('bodytimeout.pdf')) {
      res.setHeader('Content-Type','application/json');
      res.write('{"filename":');
      setTimeout(()=>res.end('"late.pdf"}'),3000);
      return;
    }
    const reply = () => {
      if (body.includes('disconnect.pdf')) return req.socket.destroy();
      if (body.includes('invalid.pdf')) return res.end('not JSON');
      res.setHeader('Content-Type', 'application/json');
      if (body.includes('failure.pdf')) { res.statusCode = 503; return res.end(JSON.stringify({detail:'Index capacity exhausted'})); }
      res.end(JSON.stringify({filename:'sample.pdf',indexed:true,total_chunks:1}));
    };
    setTimeout(reply, body.includes('timeout.pdf') ? 3000 : body.includes('slow.pdf') ? 400 : 0);
  });
});
backend.listen(8101, '127.0.0.1');
const child = spawn(process.execPath, ['node_modules/next/dist/bin/next','start','-p','3100'], {
  stdio:'inherit', env:{...process.env,DOCLENS_SESSION_SECRET:'automated-tests-only-32-character-key',BACKEND_URL:'http://127.0.0.1:8101',UPLOAD_TIMEOUT_MS:'1500',GRAFANA_PUBLIC_URL:'http://localhost:3001'}
});
for (const event of ['SIGTERM','SIGINT']) process.on(event,()=>{child.kill();backend.close();process.exit();});
child.on('exit', code=>{backend.close();process.exit(code || 0);});
