const { chromium } = require('playwright');
const path = require('path');

(async () => {
    const browser = await chromium.launch();
    const page = await browser.newPage({
        viewport: { width: 1200, height: 900 }
    });
    
    // Open the local HTML file
    const filePath = 'file://' + path.resolve('/Users/RondoT/Documents/护卫军相关/01_用户与账户体系/C端_用户签约与保密协议演示.html');
    await page.goto(filePath);
    
    // Scenario 2: Inner Modal
    await page.click('label.text-sm.text-gray-500'); // Click checkbox to open inner modal
    
    // Scroll inner modal to bottom to unlock "Agree"
    await page.evaluate(() => {
        const area = document.getElementById('innerScrollArea');
        area.scrollTop = area.scrollHeight;
    });
    
    // Wait for the button to be enabled
    await page.waitForTimeout(500);
    
    // Click inner agree button to open signature pad
    await page.click('#innerAgreeBtn');
    
    // Wait for signature pad to animate
    await page.waitForTimeout(500);
    
    // Draw something on the canvas
    const canvas = await page.$('#sigCanvasInner');
    const box = await canvas.boundingBox();
    
    await page.mouse.move(box.x + 50, box.y + 50);
    await page.mouse.down();
    await page.mouse.move(box.x + 100, box.y + 100);
    await page.mouse.move(box.x + 150, box.y + 50);
    await page.mouse.up();
    
    // Take a screenshot of the whole page showing the signature pad
    await page.screenshot({ path: '/Users/RondoT/.gemini/antigravity-ide/brain/e4794e61-011e-4a30-8340-d01927a546d7/artifacts/media_signature_demo.png' });
    
    await browser.close();
    console.log("Screenshot saved.");
})();
