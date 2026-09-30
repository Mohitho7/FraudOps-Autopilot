import { afterEach, describe, expect, it, vi } from 'vitest';
import { ApiNotConfiguredError, apiClient } from './apiClient';
import { ApiClientError, getUserFacingApiMessage } from '../types/api';

const fetchMock = vi.fn();

describe('apiClient', () => {
  afterEach(() => {
    fetchMock.mockReset();
    vi.unstubAllGlobals();
  });

  it('rejects empty endpoints without making a request', async () => {
    vi.stubGlobal('fetch', fetchMock);

    await expect(apiClient.get('')).rejects.toBeInstanceOf(ApiNotConfiguredError);
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it('normalizes unauthorized responses into a typed API error', async () => {
    fetchMock.mockResolvedValue(new Response(JSON.stringify({ detail: 'Session expired' }), { status: 401, statusText: 'Unauthorized' }));
    vi.stubGlobal('fetch', fetchMock);

    await expect(apiClient.get('http://backend.test/configured')).rejects.toMatchObject({ category: 'UNAUTHORIZED', status: 401 });
  });

  it('maps technical categories to reviewer-safe messages', () => {
    expect(getUserFacingApiMessage(new ApiClientError('TIMEOUT', 'raw timeout'), 'fallback')).toContain('too long');
    expect(getUserFacingApiMessage(new ApiClientError('SERVER_ERROR', 'raw server error'), 'fallback')).toContain('unexpected error');
  });
});
