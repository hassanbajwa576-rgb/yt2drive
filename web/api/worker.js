import { isWorker, list, del, readJson, writeJson } from './_lib.js';

export const config = { api: { bodyParser: { sizeLimit: '1mb' } } };

export default async function handler(req, res) {
  if (!isWorker(req)) return res.status(401).json({ error: 'Bad key' });
  res.setHeader('Cache-Control', 'no-store');

  if (req.method === 'GET') {
    const { blobs } = await list({ prefix: 'cmd/' });
    blobs.sort((a, b) => (a.pathname < b.pathname ? -1 : 1));
    const commands = [];
    for (const b of blobs.slice(0, 20)) {
      try {
        const c = await readJson(b.pathname);
        if (c) commands.push(c);
      } catch {}
      await del(b.url);
    }
    return res.status(200).json({ commands });
  }

  if (req.method === 'POST') {
    const s = req.body;
    if (!s || typeof s !== 'object') return res.status(400).json({ error: 'No state' });
    s.updatedAt = Date.now();
    await writeJson('status.json', s);
    return res.status(200).json({ ok: true });
  }
  return res.status(405).end();
}
