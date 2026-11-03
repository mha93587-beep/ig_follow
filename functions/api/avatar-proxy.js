/**
 * Cloudflare Pages Function
 * Route: /api/avatar-proxy?url=...
 * Proxies Instagram avatar images without referrer headers to bypass hotlink protection
 */

export async function onRequestGet(context) {
  const { request } = context;
  const url = new URL(request.url);
  const targetUrl = url.searchParams.get('url');

  if (!targetUrl) {
    return new Response('Missing target image URL', { status: 400 });
  }

  try {
    const imgResponse = await fetch(targetUrl, {
      headers: {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Referer': 'https://www.instagram.com/'
      }
    });

    if (!imgResponse.ok) {
      return new Response(`Image fetch failed with status ${imgResponse.status}`, {
        status: imgResponse.status
      });
    }

    const contentType = imgResponse.headers.get('Content-Type') || 'image/jpeg';
    
    return new Response(imgResponse.body, {
      status: 200,
      headers: {
        'Content-Type': contentType,
        'Access-Control-Allow-Origin': '*',
        'Cache-Control': 'public, max-age=86400, s-maxage=86400'
      }
    });
  } catch (error) {
    return new Response('Image proxy error: ' + error.message, { status: 502 });
  }
}
