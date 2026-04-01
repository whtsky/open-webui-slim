const { chromium } = require('playwright');

const BASE_URL = 'https://happychat.tt.codes';
const EMAIL = 'whtsky@gmail.com';
const PASSWORD = 'uC4Fb!ct';

async function waitForOneOf(page, selectors, timeout = 30000) {
	const start = Date.now();
	while (Date.now() - start < timeout) {
		for (const selector of selectors) {
			const handle = await page.$(selector);
			if (handle) return selector;
		}
		await page.waitForTimeout(200);
	}
	throw new Error(`Timed out waiting for one of selectors: ${selectors.join(', ')}`);
}

async function measure(page, name, fn) {
	const start = Date.now();
	const result = await fn();
	const end = Date.now();
	return { name, ms: end - start, result };
}

async function main() {
	const browser = await chromium.launch({ headless: true });
	const context = await browser.newContext({ viewport: { width: 1440, height: 900 } });
	const page = await context.newPage();

	await page.addInitScript(() => {
		window.__perfProbe = {
			longTasks: []
		};

		try {
			const longTaskObserver = new PerformanceObserver((list) => {
				for (const entry of list.getEntries()) {
					window.__perfProbe.longTasks.push({
						name: entry.name,
						startTime: Math.round(entry.startTime),
						duration: Math.round(entry.duration)
					});
				}
			});
			longTaskObserver.observe({ entryTypes: ['longtask'] });
		} catch {}
	});

	const requests = [];
	page.on('requestfinished', async (request) => {
		try {
			const response = await request.response();
			requests.push({
				url: request.url(),
				method: request.method(),
				status: response ? response.status() : null,
				resourceType: request.resourceType()
			});
		} catch {}
	});

	const results = {
		baseUrl: BASE_URL,
		timings: {},
		networkSummary: {},
		notes: []
	};

	results.timings.openHome = (
		await measure(page, 'openHome', async () => {
			await page.goto(BASE_URL, { waitUntil: 'networkidle', timeout: 120000 });
		})
	).ms;

	const authVisibleSelector = await waitForOneOf(
		page,
		[
			'input[type="email"]',
			'input[placeholder*="Email"]',
			'input[placeholder*="email"]',
			'#chat-input',
			'[contenteditable="true"]#chat-input'
		],
		30000
	);

	results.notes.push(`First meaningful selector: ${authVisibleSelector}`);

	if (
		authVisibleSelector !== '#chat-input' &&
		authVisibleSelector !== '[contenteditable="true"]#chat-input'
	) {
		results.timings.loginFlow = (
			await measure(page, 'loginFlow', async () => {
				const emailInput = await page
					.locator('input[type="email"], input[placeholder*="Email"], input[placeholder*="email"]')
					.first();
				const passwordInput = await page.locator('input[type="password"]').first();
				await emailInput.fill(EMAIL);
				await passwordInput.fill(PASSWORD);

				const submit = page
					.locator('button:has-text("Sign in"), button:has-text("Login"), button[type="submit"]')
					.first();
				await submit.click();

				await waitForOneOf(page, ['#chat-input', '[contenteditable="true"]#chat-input'], 120000);
				await page.waitForLoadState('networkidle', { timeout: 120000 }).catch(() => {});
			})
		).ms;
	}

	results.timings.postLoginStabilize = (
		await measure(page, 'postLoginStabilize', async () => {
			await page.waitForTimeout(3000);
		})
	).ms;

	results.timings.modelInputReady = (
		await measure(page, 'modelInputReady', async () => {
			await waitForOneOf(page, ['#chat-input', '[contenteditable="true"]#chat-input'], 30000);
		})
	).ms;

	await page.screenshot({ path: '/tmp/happychat-after-login.png', fullPage: true });

	const perfBefore = await page.evaluate(() => {
		const nav = performance.getEntriesByType('navigation')[0];
		return nav
			? {
					domContentLoaded: nav.domContentLoadedEventEnd,
					loadEventEnd: nav.loadEventEnd,
					responseEnd: nav.responseEnd
				}
			: null;
	});
	results.navigationTiming = perfBefore;

	const inputLocator = page.locator('#chat-input, [contenteditable="true"]#chat-input').first();
	const prompt = 'Please reply with exactly: hello';

	results.timings.fillPrompt = (
		await measure(page, 'fillPrompt', async () => {
			await inputLocator.click();
			const tagName = await inputLocator.evaluate((el) => el.tagName.toLowerCase());
			if (tagName === 'textarea' || tagName === 'input') {
				await inputLocator.fill(prompt);
			} else {
				await inputLocator.fill(prompt).catch(async () => {
					await page.keyboard.type(prompt);
				});
			}
		})
	).ms;

	const sendStart = Date.now();
	await page.keyboard.press('Enter');

	results.timings.firstVisibleResponseMutation = await page.evaluate(() => {
		return new Promise((resolve) => {
			const started = performance.now();
			const container = document.getElementById('messages-container') || document.body;
			let done = false;
			const observer = new MutationObserver(() => {
				if (
					!done &&
					document.querySelector('#response-message-model-name, .copy-response-button')
				) {
					done = true;
					observer.disconnect();
					resolve(Math.round(performance.now() - started));
				}
			});
			observer.observe(container, { childList: true, subtree: true, characterData: true });
			setTimeout(() => {
				if (!done) {
					observer.disconnect();
					resolve(null);
				}
			}, 120000);
		});
	});

	const beforeCount = await page
		.locator('.copy-response-button')
		.count()
		.catch(() => 0);
	results.notes.push(`Copy buttons before send: ${beforeCount}`);

	await page.waitForFunction(
		(count) => document.querySelectorAll('.copy-response-button').length > count,
		beforeCount,
		{ timeout: 120000 }
	);
	results.timings.timeToCompletedAssistantMessage = Date.now() - sendStart;
	results.timings.chatDomNodeCount = await page.evaluate(
		() => document.querySelectorAll('*').length
	);

	await page.screenshot({ path: '/tmp/happychat-after-chat.png', fullPage: true });

	const perfMetrics = await page.evaluate(() => {
		const nav = performance.getEntriesByType('navigation')[0];
		const resources = performance.getEntriesByType('resource');
		return {
			navigation: nav
				? {
						domContentLoaded: nav.domContentLoadedEventEnd,
						loadEventEnd: nav.loadEventEnd,
						transferSize: nav.transferSize,
						encodedBodySize: nav.encodedBodySize,
						decodedBodySize: nav.decodedBodySize
					}
				: null,
			resourceCount: resources.length,
			slowResources: resources
				.filter((r) => r.duration > 300)
				.sort((a, b) => b.duration - a.duration)
				.slice(0, 15)
				.map((r) => ({
					name: r.name,
					duration: Math.round(r.duration),
					initiatorType: r.initiatorType
				}))
		};
	});
	results.performanceEntries = perfMetrics;
	results.browserMainThread = await page.evaluate(() => {
		const longTasks = (window.__perfProbe && window.__perfProbe.longTasks) || [];
		return {
			longTaskCount: longTasks.length,
			totalLongTaskTime: longTasks.reduce((sum, task) => sum + task.duration, 0),
			worstLongTasks: longTasks.sort((a, b) => b.duration - a.duration).slice(0, 10)
		};
	});

	const apiRequests = requests.filter((r) => /\/api\//.test(r.url));
	results.networkSummary = {
		totalRequests: requests.length,
		apiRequests: apiRequests.length,
		failedRequests: requests.filter((r) => r.status && r.status >= 400).slice(0, 20),
		topApiEndpoints: apiRequests.slice(-30)
	};

	console.log(JSON.stringify(results, null, 2));
	await browser.close();
}

main().catch((err) => {
	console.error(err);
	process.exit(1);
});
