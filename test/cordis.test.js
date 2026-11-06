import test from 'node:test';
import assert from 'node:assert/strict';
import { Context } from '@deepseek-ai/cordis';
import ToolsService from '@deepseek-ai/dsh-tools';
import SystemPrompt from '@deepseek-ai/dsh-system-prompt';
import * as alaya from '../index.js';

test('real Cordis loads Alaya, exposes tools and unregisters them on unload', async () => {
  const ctx = new Context();
  try {
    await ctx.plugin(SystemPrompt);
    await ctx.plugin(ToolsService);
    const fiber = await ctx.plugin(alaya, {});
    assert.equal(fiber.state, 2);
    assert.equal(ctx.tools.schemas().length, 5);
    const guide = ctx.tools.get('alaya_guide');
    const value = await guide.execute({ topic: 'router' }, { signal: new AbortController().signal });
    assert.match(value, /Alaya/);
    await fiber.dispose();
    assert.equal(ctx.tools.get('alaya_guide'), undefined);
    assert.equal(ctx.tools.schemas().length, 0);
  } finally {
    await ctx.fiber.dispose();
  }
});
