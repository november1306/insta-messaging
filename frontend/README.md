# Instagram Messenger Frontend

Vue 3 + Vite frontend for the Instagram Messenger Automation system.

## Setup

### 1. Install Dependencies

```bash
npm install
```

### 2. Configure API Key

Create a `.env` file from the example:

```bash
cp .env.example .env
```

Then choose one of the following options:

#### Option A: Use Stub Authentication (Development)

1. Enable stub auth in the backend `.env` file:
   ```
   USE_STUB_AUTH=true
   ```
2. The default `demo-token` in frontend `.env` will work

#### Option B: Use Real API Key

1. Generate an API key from the backend:
   ```bash
   # From project root
   python -m app.cli.generate_api_key --name "Frontend Dev" --type admin --env test
   ```

2. Copy the generated key and update frontend `.env`:
   ```
   VITE_API_KEY=sk_test_your_generated_key_here
   ```

### 3. Run Development Server

```bash
npm run dev
```

### 4. Build for Production

```bash
npm run build
```

## Environment Variables

- `VITE_API_KEY` - API key for backend authentication (default: `demo-token`)

## Learn More

- [Vue 3 Script Setup](https://v3.vuejs.org/api/sfc-script-setup.html)
- [Vue 3 IDE Support](https://vuejs.org/guide/scaling-up/tooling.html#ide-support)
- [Authentication Guide](../AUTHENTICATION.md)
