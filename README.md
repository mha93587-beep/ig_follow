# InstaGrowth Pro - Live Profile Counter & Follower Delivery Flow

A high-conversion, responsive Instagram growth landing page with real-time profile lookup using SearchApi.io and live animated follower counter.

## Features
- **Real-time Instagram Stats**: Dynamically retrieves profile avatars, follower counts, following, post counts, bio, and verified badges.
- **Strict Domain-Level API Protection**: External bots, unauthorized servers, or scraper domains receive `401 Unauthorized`. Only your frontend domain can access the API.
- **Cloudflare Pages Native**: Serverless edge functions (`functions/api/profile.js` and `functions/api/avatar-proxy.js`) for global edge deployment.
- **Local Server Included**: Lightweight zero-dependency Python server for local testing.
- **Security First**: No hardcoded API keys; `.env` is ignored by git.

## Local Development
1. Clone the repository:
   ```bash
   git clone https://github.com/mha93587-beep/ig_follow.git
   cd ig_follow
   ```
2. Create a `.env` file from `.env.example`:
   ```bash
   cp .env.example .env
   ```
   Add your SearchApi key:
   ```env
   SEARCHAPI_API_KEY=your_searchapi_key
   ```
3. Start the local server:
   ```bash
   python3 server.py
   ```
4. Open `http://localhost:5000` in your browser.

## Cloudflare Pages Deployment
1. Connect this GitHub repository to **Cloudflare Pages**.
2. **Build Settings**:
   - Framework preset: `None`
   - Build command: *(leave empty)*
   - Build output directory: `.`
3. In **Settings** > **Environment variables**:
   - Add `SEARCHAPI_API_KEY` = your SearchApi key.
4. Deploy! Your static assets and edge functions will be live globally.
