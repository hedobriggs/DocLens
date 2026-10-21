// One-shot private setup and frontend entrypoint. No shell evaluation or network.
const fs = require('node:fs');
const path = require('node:path');
const crypto = require('node:crypto');
const {createRequire} = require('node:module');
const appRequire = () => createRequire(path.join(process.cwd(), 'package.json'));

function inputConfig(text) {
  const values = {};
  for (const line of text.split(/\r?\n/)) {
    if (!line.trim() || line.trim().startsWith('#')) continue;
    const match = line.match(/^([A-Z_][A-Z0-9_]*)=(.*)$/);
    if (!match) throw Error('Invalid private configuration line');
    const [,key,raw] = match;
    if (Object.hasOwn(values,key)) throw Error('Duplicate private configuration key');
    let value = raw.trim();
    if (value.startsWith("'") || value.startsWith('"')) {
      if (value.length < 2 || value.at(-1)!==value[0]) throw Error('Unclosed private configuration quote');
      value = value.slice(1,-1);
    }
    values[key]=value;
  }
  const email=values.DOCLENS_ADMIN_EMAIL, password=values.DOCLENS_ADMIN_PASSWORD, key=values.GEMINI_API_KEY;
  if (!email || !email.includes('@') || email.endsWith('.example') || !password ||
      Array.from(password).length<12 || Buffer.byteLength(password)>72 ||
      !key || [email,password,key].some(v=>/[\r\n\0]/.test(v)||/^replace-with/i.test(v))) {
    throw Error('Set a real admin email, password (12+ characters, at most 72 UTF-8 bytes), and Gemini key in the private .env file');
  }
  return {email,password,key};
}

function regular(file) {
  if (!fs.lstatSync(file).isFile() || fs.lstatSync(file).isSymbolicLink()) throw Error('Refuse non-regular private configuration');
  return fs.readFileSync(file,'utf8');
}

function initialize(config, index, input) {
  const {email,password,key} = inputConfig(regular(input));
  const bcrypt=appRequire()('bcryptjs');
  const ready=path.join(config,'ready.json');
  if (fs.existsSync(ready)) {
    if (JSON.parse(regular(ready)).version!==1) throw Error('Unsupported saved configuration version');
    const frontend=JSON.parse(regular(path.join(config,'frontend/settings.json')));
    const backend=JSON.parse(regular(path.join(config,'backend/settings.json')));
    if (typeof frontend.DOCLENS_SESSION_SECRET!=='string' || frontend.DOCLENS_SESSION_SECRET.length<32) throw Error('Incomplete saved settings; preserve the configuration volume for recovery');
    if (frontend.DOCLENS_ADMIN_EMAIL.toLowerCase()!==email.toLowerCase() ||
        !bcrypt.compareSync(password,frontend.DOCLENS_ADMIN_PASSWORD_HASH) ||
        backend.GEMINI_API_KEY!==key ||
        frontend.DOCLENS_SESSION_SECRET!==backend.DOCLENS_SESSION_SECRET) {
      throw Error('Saved settings differ from .env; no credentials or documents changed. Restore the matching private file before starting');
    }
    return 'Existing private settings preserved';
  }
  if (fs.readdirSync(config).length) throw Error('Incomplete saved setup; preserve the configuration volume for recovery');
  if (fs.readdirSync(index).length) throw Error('Existing index has no matching automatic configuration. Use the previous configured installation; no migration or credential reset was performed');
  const session=crypto.randomBytes(48).toString('base64url');
  const settings={
    backend:{uid:10001,values:{DOCLENS_SESSION_SECRET:session,GEMINI_API_KEY:key}},
    frontend:{uid:1000,values:{DOCLENS_SESSION_SECRET:session,DOCLENS_ADMIN_EMAIL:email,
      DOCLENS_ADMIN_PASSWORD_HASH:bcrypt.hashSync(password,12)}},
  };
  fs.chmodSync(config,0o755);
  for (const [role,{uid,values}] of Object.entries(settings)) {
    const folder=path.join(config,role);fs.mkdirSync(folder,{mode:0o700});
    const file=path.join(folder,'settings.json');
    fs.writeFileSync(file,JSON.stringify(values),{mode:0o400,flag:'wx'});
    fs.chownSync(file,uid,uid);fs.chownSync(folder,uid,uid);
  }
  fs.writeFileSync(ready,JSON.stringify({version:1}),{mode:0o600,flag:'wx'});
  return 'Private settings initialized; no document data changed';
}

function frontend() {
  const values=JSON.parse(regular('/config/frontend/settings.json'));
  for (const key of ['DOCLENS_SESSION_SECRET','DOCLENS_ADMIN_EMAIL','DOCLENS_ADMIN_PASSWORD_HASH']) {
    if (typeof values[key]!=='string'||!values[key]) throw Error('Incomplete frontend configuration');
    process.env[key]=values[key];
  }
  const next=appRequire().resolve('next/dist/bin/next');
  process.argv=[process.execPath,next,'start','--hostname','0.0.0.0','--port','3000'];
  require(next);
}

module.exports={inputConfig,initialize};
if(require.main===module) {
  try {
    if(process.argv[2]==='setup') console.log(initialize('/config','/existing-index','/run/secrets/initial_config'));
    else if(process.argv[2]==='frontend') frontend();
    else throw Error('Unknown bootstrap component');
  } catch(error) {
    // Only deliberate validation errors are printable; filesystem/provider data is not.
    console.error('DocLens setup/start failed ('+error.constructor.name+'): '+
      (error.constructor===Error ? error.message : 'Private configuration could not be read; preserve files and volumes'));
    process.exitCode=1;
  }
}
