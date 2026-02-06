# Deploying to GitHub Pages

This guide explains how to deploy the Pulsecity landing page to GitHub Pages.

## Automatic Deployment (Recommended)

The project includes GitHub Actions workflow that automatically deploys on every push to `main`.

### Setup:

1. **Enable GitHub Pages in your repository:**
   - Go to Settings → Pages
   - Under "Build and deployment"
   - Set Source to: **Deploy from a branch**
   - Set Branch to: **gh-pages** (GitHub Actions will create this)

2. **That's it!** Push to main and GitHub Actions will automatically build and deploy.

## Manual Deployment

If you want to deploy manually:

```bash
# Build the static site
npm run build

# The output is in the `out` folder
# Upload the contents of `out/` to gh-pages branch or your hosting provider
```

## View Your Site

- **If deployed to user/org pages:** `https://<username>.github.io/`
- **If deployed to project (subdirectory):** `https://<username>.github.io/event-intelligence-platform/`

You can set a custom domain in Settings → Pages.

## Troubleshooting

### Page not showing?
- Check "Actions" tab to see if deployment succeeded
- Verify GitHub Pages is enabled and set to deploy from gh-pages branch
- Wait a few minutes for GitHub Pages to publish

### Styling looks broken?
- Make sure Tailwind CSS built correctly in the build logs
- Check that `output: "export"` is set in `next.config.ts`

### Images not loading?
- GitHub Pages path requires the repo name in the URL for non-user repos
- Images are already optimized for static export via `unoptimized: true`

## Environment Variables

If this ever needs environment variables, add them as GitHub Secrets:
1. Settings → Secrets and variables → Actions
2. Add your secret names matching those in `.env.local`
3. GitHub Actions will inject them during build
