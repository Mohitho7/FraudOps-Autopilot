import { afterEach, describe, expect, it, vi } from 'vitest';
import { ApiNotConfiguredError, apiClient } from './apiClient';

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
});
