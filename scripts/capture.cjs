const puppeteer = require('../frontend/node_modules/puppeteer-core')
const fs = require('fs')
const path = require('path')

const CHROME_PATH = 'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe'
const OUT_DIR = path.resolve(__dirname, '../screenshots')
const TOKENS_FILE = path.resolve(__dirname, '../screenshots_tokens.json')

const delay = (ms) => new Promise((resolve) => setTimeout(resolve, ms))

async function run() {
  const tokens = JSON.parse(fs.readFileSync(TOKENS_FILE, 'utf8'))

  const browser = await puppeteer.launch({
    executablePath: CHROME_PATH,
    headless: 'new',
    defaultViewport: { width: 1320, height: 860, deviceScaleFactor: 2 },
    args: [
      '--no-sandbox',
      '--disable-setuid-sandbox',
      '--disable-gpu',
      '--disable-dev-shm-usage',
      '--no-first-run',
      '--no-default-browser-check',
    ],
  })

  const page = await browser.newPage()

  async function setSession(userObj, token) {
    await page.goto('http://localhost:5173/login', { waitUntil: 'networkidle0' })
    await page.evaluate((u, t) => {
      localStorage.setItem('token', t)
      localStorage.setItem('user', JSON.stringify(u))
    }, userObj, token)
  }

  // 1. Login
  console.log('Capturing: 01_login_portal.png...')
  await page.goto('http://localhost:5173/login', { waitUntil: 'networkidle0' })
  await delay(800)
  await page.screenshot({ path: path.join(OUT_DIR, '01_login_portal.png'), fullPage: false })

  // 2. Register
  console.log('Capturing: 02_user_registration.png...')
  await page.goto('http://localhost:5173/register', { waitUntil: 'networkidle0' })
  await delay(800)
  await page.screenshot({ path: path.join(OUT_DIR, '02_user_registration.png'), fullPage: false })

  // --- Customer Views ---
  console.log('Logging in as Customer...')
  await setSession(tokens.customer.user, tokens.customer.token)

  // 3. Customer Home
  console.log('Capturing: 03_customer_home.png...')
  await page.goto('http://localhost:5173/customer/dashboard', { waitUntil: 'networkidle0' })
  await delay(1200)
  await page.screenshot({ path: path.join(OUT_DIR, '03_customer_home.png'), fullPage: false })

  // 4. Service Catalog
  console.log('Capturing: 04_service_catalog.png...')
  await page.goto('http://localhost:5173/customer/services', { waitUntil: 'networkidle0' })
  await delay(1200)
  await page.screenshot({ path: path.join(OUT_DIR, '04_service_catalog.png'), fullPage: false })

  // 5. Expert Discovery
  console.log('Capturing: 05_expert_discovery.png...')
  await page.goto('http://localhost:5173/customer/experts', { waitUntil: 'networkidle0' })
  await delay(1000)
  // Fill manual coordinates with focus + type to trigger React controlled input
  await page.focus('input[placeholder="e.g. 17.44000"]')
  await page.keyboard.type('17.44000')
  await page.focus('input[placeholder="e.g. 78.39000"]')
  await page.keyboard.type('78.39000')
  const searchBtn = await page.$('button.btn-primary')
  if (searchBtn) await searchBtn.click()
  await delay(2000)
  await page.screenshot({ path: path.join(OUT_DIR, '05_expert_discovery.png'), fullPage: false })

  // 6. Schedule Booking Form
  console.log('Capturing: 06_schedule_booking.png...')
  // Click "Book Expert" button on the first expert card
  const bookBtn = await page.evaluateHandle(() => {
    return Array.from(document.querySelectorAll('button')).find((b) => b.textContent.includes('Book Expert'))
  })
  if (bookBtn && bookBtn.asElement()) {
    await bookBtn.asElement().click()
    await delay(1500)
  } else {
    await page.goto('http://localhost:5173/customer/book/new', { waitUntil: 'networkidle0' })
    await delay(1000)
  }
  await page.screenshot({ path: path.join(OUT_DIR, '06_schedule_booking.png'), fullPage: false })

  // 7. My Bookings
  console.log('Capturing: 07_my_bookings.png...')
  await page.goto('http://localhost:5173/customer/bookings', { waitUntil: 'networkidle0' })
  await delay(1500)
  await page.screenshot({ path: path.join(OUT_DIR, '07_my_bookings.png'), fullPage: false })

  // 8. AI Assistant Copilot
  console.log('Capturing: 08_ai_assistant_copilot.png...')
  await page.goto('http://localhost:5173/customer/assistant', { waitUntil: 'networkidle0' })
  await delay(1000)
  // Click first suggestion chip if present
  try {
    const chip = await page.$('.ai-chip')
    if (chip) {
      await chip.click()
      await delay(4000)
    }
  } catch (e) {
    console.log('AI chip click skipped:', e.message)
  }
  await page.screenshot({ path: path.join(OUT_DIR, '08_ai_assistant_copilot.png'), fullPage: false })

  // 9. Real-time Chat
  console.log('Capturing: 09_realtime_chat.png...')
  await page.goto('http://localhost:5173/customer/bookings/18/chat', { waitUntil: 'networkidle0' })
  await delay(2000)
  await page.screenshot({ path: path.join(OUT_DIR, '09_realtime_chat.png'), fullPage: false })

  // 10. Live GPS Tracking
  console.log('Capturing: 10_live_gps_tracking.png...')
  await page.goto('http://localhost:5173/customer/bookings/18/tracking', { waitUntil: 'networkidle0' })
  await delay(3000)
  await page.screenshot({ path: path.join(OUT_DIR, '10_live_gps_tracking.png'), fullPage: false })

  // 11. Notification Center
  console.log('Capturing: 11_notification_center.png...')
  await page.goto('http://localhost:5173/customer/dashboard', { waitUntil: 'networkidle0' })
  await delay(1000)
  const bell = await page.$('.notif-bell-btn')
  if (bell) {
    await bell.click()
    await delay(700)
  }
  await page.screenshot({ path: path.join(OUT_DIR, '11_notification_center.png'), fullPage: false })

  // --- Expert Views ---
  console.log('Logging in as Expert...')
  await setSession(tokens.expert.user, tokens.expert.token)

  // 12. Expert Dashboard
  console.log('Capturing: 12_expert_dashboard.png...')
  await page.goto('http://localhost:5173/expert/dashboard', { waitUntil: 'networkidle0' })
  await delay(1500)
  await page.screenshot({ path: path.join(OUT_DIR, '12_expert_dashboard.png'), fullPage: false })

  // 13. Expert Profile Editor
  console.log('Capturing: 13_expert_profile.png...')
  await page.goto('http://localhost:5173/expert/profile', { waitUntil: 'networkidle0' })
  await delay(1500)
  await page.screenshot({ path: path.join(OUT_DIR, '13_expert_profile.png'), fullPage: false })

  // --- Admin Views ---
  console.log('Logging in as Admin...')
  await setSession(tokens.admin.user, tokens.admin.token)

  // 14. Admin Control Center
  console.log('Capturing: 14_admin_dashboard.png...')
  await page.goto('http://localhost:5173/admin/dashboard', { waitUntil: 'networkidle0' })
  await delay(1500)
  await page.screenshot({ path: path.join(OUT_DIR, '14_admin_dashboard.png'), fullPage: false })

  await browser.close()
  console.log('All screenshots captured successfully!')
}

run().catch((err) => {
  console.error('Error during capture:', err)
  process.exit(1)
})
