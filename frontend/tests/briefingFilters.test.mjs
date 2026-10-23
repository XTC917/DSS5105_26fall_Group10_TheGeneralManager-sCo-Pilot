import test from 'node:test';
import assert from 'node:assert/strict';
import { filterOrders, deadlineText } from '../src/components/briefingFilters.mjs';
const orders = [
  { order_id: 'A', current_stage: 'KNITTING', flags: ['STALLED'], bucket: 'LATER' },
  { order_id: 'B', current_stage: 'WASHING', flags: ['OVERDUE', 'STALLED'], bucket: 'OVERDUE' },
  { order_id: 'C', current_stage: 'WASHING', flags: [], bucket: 'TODAY' },
  { order_id: 'D', current_stage: 'PACKING', flags: [], bucket: 'TWO_DAYS' },
];
test('stalled knitting cannot include washing orders', () => {
  assert.deepEqual(filterOrders(orders, 'STALLED', 'KNITTING').map(r => r.order_id), ['A']);
  assert.deepEqual(filterOrders(orders, 'ALL', 'WASHING').map(r => r.order_id), ['B', 'C']);
  assert.deepEqual(filterOrders(orders, 'OVERDUE').map(r => r.order_id), ['B']);
  assert.deepEqual(filterOrders(orders, 'SOON').map(r => r.order_id), ['C', 'D']);
  assert.deepEqual(filterOrders(orders, 'STALLED', 'PACKING'), []);
  assert.equal(filterOrders(orders).length, 4);
});
test('deadline wording handles overdue, today, future and missing values', () => {
  assert.equal(deadlineText(-9), 'Overdue by 9 days');
  assert.equal(deadlineText(-1), 'Overdue by 1 day');
  assert.equal(deadlineText(1), 'Due today');
  assert.equal(deadlineText(2), 'Due in 2 days');
  assert.equal(deadlineText(3), 'Due in 3 days');
  assert.equal(deadlineText(null), 'Due date unavailable');
});
