import { isPanelAuthed, writeJson } from './_lib.js';
import crypto from 'node:crypto';

const URL_OK = /^https?:\/\/[^\s"'<>]{4,300}$/i;

export default async function handler(req, res) {
  if (req.method !== 'POST') return res.status(405).end();
  if (!isPanelAuthed(req)) return res.status(401).json({ error: 'Not signed in' });
  if (req.headers['x-requested-with'] !== 'panel') return res.status(400).json({ error: 'Bad request' });

  const b = req.body || {};
  const o = b.opts || {};
  const opts = {
    reencode: !!o.reencode,
    keep: !!o.keep,
    skip_done: o.skip_done !== false,
    caption: String(o.caption || '').slice(0, 500),
  };
  let cmd;
  if (b.type === 'find') {
    cmd = {
      type: 'find',
      count: Math.max(1, Math.min(200, Number(b.count) || 50)),
      topics: String(b.topics || '').slice(0, 1000),
      cc_only: !!b.cc_only,
      auto: !!b.auto,
      opts,
    };
  } else if (b.type === 'start') {
    const urls = (Array.isArray(b.urls) ? b.urls : []).map(String).filter((u) => URL_OK.test(u)).slice(0, 200);
    if (!urls.length) return res.status(400).json({ error: 'No valid links' });
    cmd = { type: 'start', urls, opts };
  } else if (b.type === 'cancel') {
    cmd = { type: 'cancel' };
  } else {
    return res.status(400).json({ error: 'Unknown command' });
  }
  const id = `${Date.now()}-${crypto.randomBytes(3).toString('hex')}`;
  await writeJson(`cmd/${id}.json`, { id, ...cmd });
  return res.status(200).json({ ok: true, id });
}
