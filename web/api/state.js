import { isPanelAuthed, readJson } from './_lib.js';

export default async function handler(req, res) {
  if (!isPanelAuthed(req)) return res.status(401).json({ error: 'Not signed in' });
  res.setHeader('Cache-Control', 'no-store');
  const state = await readJson('status.json');
  return res.status(200).json({ now: Date.now(), state });
}
