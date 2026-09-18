import assert from 'node:assert/strict';
import test from 'node:test';
import { clinicalSyncDecision } from './clinical-sync.ts';

test('clean doctor screen accepts secretary update', () => {
  assert.equal(clinicalSyncDecision('old', 'old', 'new', false), 'apply');
});
test('typing even before debounce is protected from remote overwrite', () => {
  assert.equal(clinicalSyncDecision('typing', 'old', 'new', false), 'conflict');
});
test('unrelated events do not conflict with local edits', () => {
  assert.equal(clinicalSyncDecision('typing', 'old', 'old', false), 'unchanged');
});
test('pending save defers remote updates', () => {
  assert.equal(clinicalSyncDecision('old', 'old', 'new', true), 'conflict');
});
