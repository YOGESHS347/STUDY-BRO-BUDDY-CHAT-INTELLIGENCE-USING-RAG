import { chromium } from 'playwright';
import path from 'path';

const outDir = 'C:\\Users\\yoges\\.gemini\\antigravity-ide\\brain\\cc3873dd-b444-4e29-ac9a-a25f3f443788';

async function run() {
  console.log('Launching Edge browser...');
  const browser = await chromium.launch({
    channel: 'msedge',
    headless: true,
  });

  const context = await browser.newContext({
    viewport: { width: 1440, height: 900 },
    deviceScaleFactor: 1,
  });

  const page = await context.newPage();

  // 1. Login Page
  console.log('Navigating to login...');
  await page.goto('http://localhost:5173/login', { waitUntil: 'networkidle' });
  await page.waitForTimeout(1000);
  await page.screenshot({ path: path.join(outDir, 'login_cinematic.png') });
  console.log('Saved login_cinematic.png');

  // 2. Sign in
  console.log('Signing in...');
  await page.fill('input[type="email"]', 'testuser_rag@gmail.com');
  await page.fill('input[type="password"]', 'TestPass123!');
  await page.click('button[type="submit"]');

  // Wait for redirect to dashboard
  await page.waitForURL('**/dashboard', { timeout: 15000 });
  await page.waitForTimeout(1500); // Allow entrance animations to settle
  await page.screenshot({ path: path.join(outDir, 'dashboard_cinematic.png') });
  console.log('Saved dashboard_cinematic.png');

  // 3. Documents Page
  console.log('Navigating to documents...');
  await page.click('a[href="/documents"]');
  await page.waitForURL('**/documents', { timeout: 10000 });
  await page.waitForTimeout(1000);
  await page.screenshot({ path: path.join(outDir, 'documents_cinematic.png') });
  console.log('Saved documents_cinematic.png');

  // 4. Chat Workspace
  console.log('Navigating to chat...');
  await page.click('a[href="/chat"]');
  await page.waitForURL('**/chat', { timeout: 10000 });
  await page.waitForTimeout(1000);
  await page.screenshot({ path: path.join(outDir, 'chat_cinematic.png') });
  console.log('Saved chat_cinematic.png');

  // 5. Click New Chat button to initialize conversation
  console.log('Clicking New Chat...');
  const newChatBtn = page.locator('button:has-text("New Chat")');
  if (await newChatBtn.isVisible()) {
    await newChatBtn.click();
    await page.waitForTimeout(1000);
  }

  // 6. Send a question
  console.log('Typing question in chat...');
  const textarea = page.locator('textarea[aria-label="Message input"]');
  if (await textarea.isVisible() && !(await textarea.isDisabled())) {
    await textarea.fill('Summarize the document intelligence RAG system architecture.');
    await page.click('button[aria-label="Send question"]');
    console.log('Waiting for generation...');
    try {
      await page.waitForSelector('.markdown-pro-content', { timeout: 35000 });
      await page.waitForTimeout(1000);
    } catch {
      console.log('Generation completed or wait limit reached.');
    }
    await page.screenshot({ path: path.join(outDir, 'chat_answered_cinematic.png') });
    console.log('Saved chat_answered_cinematic.png');
  }

  // 7. Light Mode
  console.log('Switching to light mode...');
  const lightBtn = page.locator('button[aria-label="Light theme"]');
  if (await lightBtn.isVisible()) {
    await lightBtn.click();
    await page.waitForTimeout(800);
    await page.screenshot({ path: path.join(outDir, 'light_mode_cinematic.png') });
    console.log('Saved light_mode_cinematic.png');

    // Switch back to dark mode
    const darkBtn = page.locator('button[aria-label="Dark theme"]');
    await darkBtn.click();
    await page.waitForTimeout(500);
  }

  // 8. Mobile Layout
  console.log('Testing mobile viewport...');
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto('http://localhost:5173/dashboard', { waitUntil: 'networkidle' });
  await page.waitForTimeout(800);
  // Open mobile drawer
  const menuBtn = page.locator('button[aria-label="Toggle navigation menu"]');
  if (await menuBtn.isVisible()) {
    await menuBtn.click();
    await page.waitForTimeout(600);
  }
  await page.screenshot({ path: path.join(outDir, 'mobile_drawer_cinematic.png') });
  console.log('Saved mobile_drawer_cinematic.png');

  await browser.close();
  console.log('ALL SCREENSHOTS CAPTURED SUCCESSFULLY!');
}

run().catch((err) => {
  console.error('QA script error:', err);
  process.exit(1);
});
