import { isPanelAuthed, makeSession, safeEq } from './_lib.js';

const cookie = (v, age) =>
  `panel=${v}; Path=/; HttpOnly; Secure; SameSite=Strict; Max-Age=${age}`;

export default async function handler(req, res) {
  if (req.method === 'GET') return res.status(200).json({ authed: isPanelAuthed(req) });
  if (req.method === 'DELETE') {
    res.setHeader('Set-Cookie', cookie('', 0));
    return res.status(200).json({ ok: true });
  }
  if (req.method !== 'POST') return res.status(405).end();
  const pw = req.body?.password;
  if (process.env.PANEL_PASSWORD && safeEq(pw, process.env.PANEL_PASSWORD)) {
    res.setHeader('Set-Cookie', cookie(makeSession(), 7 * 24 * 3600));
    return res.status(200).json({ ok: true });
  }
  await new Promise((r) => setTimeout(r, 1200)); // slow down guessing
  return res.status(401).json({ error: 'Wrong password' });
}
