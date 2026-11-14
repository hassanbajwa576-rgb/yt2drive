import crypto from 'node:crypto';
import { put, get, list, del } from '@vercel/blob';

const WEEK = 7 * 24 * 3600 * 1000;

function hmac(v) {
  return crypto.createHmac('sha256', process.env.SESSION_SECRET || '').update(v).digest('hex');
}

export function safeEq(a, b) {
  const x = crypto.createHash('sha256').update(String(a ?? '')).digest();
  const y = crypto.createHash('sha256').update(String(b ?? '')).digest();
  return crypto.timingSafeEqual(x, y);
}

export function makeSession() {
  const ts = Date.now();
  return `${ts}.${hmac(String(ts))}`;
}

function parseCookies(req) {
  const out = {};
  for (const part of String(req.headers.cookie || '').split(';')) {
    const i = part.indexOf('=');
    if (i > 0) out[part.slice(0, i).trim()] = part.slice(i + 1).trim();
  }
  return out;
}

export function isPanelAuthed(req) {
  if (!process.env.SESSION_SECRET) return false;
  const tok = parseCookies(req).panel || '';
  const [ts, sig] = tok.split('.');
  if (!ts || !sig || Date.now() - Number(ts) > WEEK) return false;
  return safeEq(sig, hmac(ts));
}

export function isWorker(req) {
  const key = process.env.WORKER_KEY;
  return !!key && safeEq(req.headers['x-worker-key'], key);
}

export async function readJson(pathname) {
  const r = await get(pathname, { access: 'private', useCache: false });
  if (!r || r.statusCode !== 200) return null;
  return JSON.parse(await new Response(r.stream).text());
}

export async function writeJson(pathname, obj) {
  await put(pathname, JSON.stringify(obj), {
    access: 'private',
    addRandomSuffix: false,
    allowOverwrite: true,
    contentType: 'application/json',
    cacheControlMaxAge: 60,
  });
}

export { list, del };
