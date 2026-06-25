import { ChakraProvider } from '@chakra-ui/react';
import { fireEvent, render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';

import { system } from '../theme';

const XML = `<?xml version="1.0"?>
<context name="local" description="Emulated Context">
  <device id="iio:device0" name="ad7291">
    <channel id="voltage0" type="input">
      <attribute name="raw" value="2048"/>
    </channel>
  </device>
</context>`;

vi.mock('../api/queries', () => ({
  useRunLogs: () => ({ data: [] }),
  useArtifactRaw: () => ({ data: XML, isLoading: false, isError: false }),
}));

import { ContextXmlBody } from './ContextXmlViewer';

function renderBody() {
  return render(
    <ChakraProvider value={system}>
      <ContextXmlBody artifactId="a1" filename="ad7291.xml" open={true} />
    </ChakraProvider>,
  );
}

describe('ContextXmlBody', () => {
  it('drills from device into channel into attribute', () => {
    renderBody();
    // device shown; channel hidden until the device is expanded
    expect(screen.getByRole('button', { name: /ad7291/ })).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: /voltage0/ })).toBeNull();

    fireEvent.click(screen.getByRole('button', { name: /ad7291/ }));
    expect(screen.getByRole('button', { name: /voltage0/ })).toBeInTheDocument();
    expect(screen.queryByText('raw = 2048')).toBeNull();

    fireEvent.click(screen.getByRole('button', { name: /voltage0/ }));
    expect(screen.getByText('raw = 2048')).toBeInTheDocument();
  });

  it('toggles to the raw XML view', () => {
    renderBody();
    fireEvent.click(screen.getByRole('button', { name: /^Raw$/ }));
    expect(screen.getByText(/<context name="local"/)).toBeInTheDocument();
  });

  it('offers a download link to the raw artifact', () => {
    renderBody();
    const link = screen.getByRole('link', { name: /download/i });
    expect(link).toHaveAttribute('href', '/api/v1/artifacts/a1/raw');
    expect(link).toHaveAttribute('download', 'ad7291.xml');
  });
});
