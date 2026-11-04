/**
 * Cloudflare Pages Function
 * Route: /api/config
 * Returns application configuration (such as WEB_MODE: 'PUBLIC' or 'Creator')
 */

export async function onRequestGet(context) {
  const { request, env } = context;
  const url = new URL(request.url);
  const currentOrigin = request.headers.get('origin') || `${url.protocol}//${url.host}`;

  const mode = (env.WEB_MODE || 'PUBLIC').trim();

  return new Response(JSON.stringify({
    status: 'success',
    web_mode: mode
  }), {
    status: 200,
    headers: {
      'Content-Type': 'application/json; charset=utf-8',
      'Access-Control-Allow-Origin': currentOrigin,
      'Access-Control-Allow-Methods': 'GET, OPTIONS',
      'Access-Control-Allow-Headers': 'Content-Type, X-Requested-With',
      'Cache-Control': 'public, max-age=60'
    }
  });
}

export async function onRequestOptions(context) {
  const { request } = context;
  const url = new URL(request.url);
  const currentOrigin = request.headers.get('origin') || `${url.protocol}//${url.host}`;

  return new Response(null, {
    status: 204,
    headers: {
      'Access-Control-Allow-Origin': currentOrigin,
      'Access-Control-Allow-Methods': 'GET, OPTIONS',
      'Access-Control-Allow-Headers': 'Content-Type, X-Requested-With'
    }
  });
}
