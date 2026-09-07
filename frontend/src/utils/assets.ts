import { CryptoAsset } from '../types';

export interface CryptoAssetMeta {
  id: CryptoAsset;
  symbol: string;
  label: string;
  name: string;
  color: string;
  bgGrad: string;
  decimals: number;
  minSpotDiff: number;
  defaultBuffer: number;
  minBuffer: number;
  deltaOffsets: number[];
  thresholdGuideline: number;
}

export const CRYPTO_ASSETS: Record<CryptoAsset, CryptoAssetMeta> = {
  BTC: {
    id: 'BTC',
    symbol: '₿',
    label: 'BTC',
    name: 'Bitcoin',
    color: '#f7931a',
    bgGrad: 'from-[#f7931a] to-[#e67e00]',
    decimals: 2,
    minSpotDiff: 35.0,
    defaultBuffer: 35.0,
    minBuffer: 10.0,
    deltaOffsets: [64, 50, 30, 10, 6, 1, 0, -6, -10, -30, -50],
    thresholdGuideline: 50,
  },
  ETH: {
    id: 'ETH',
    symbol: 'Ξ',
    label: 'ETH',
    name: 'Ethereum',
    color: '#627eea',
    bgGrad: 'from-[#627eea] to-[#3b5998]',
    decimals: 2,
    minSpotDiff: 2.5,
    defaultBuffer: 5.0,
    minBuffer: 1.0,
    deltaOffsets: [15, 10, 5, 2.5, 1, 0, -1, -2.5, -5, -10, -15],
    thresholdGuideline: 5.0,
  },
  SOL: {
    id: 'SOL',
    symbol: '◎',
    label: 'SOL',
    name: 'Solana',
    color: '#14f195',
    bgGrad: 'from-[#9945ff] to-[#14f195]',
    decimals: 2,
    minSpotDiff: 0.5,
    defaultBuffer: 1.5,
    minBuffer: 0.25,
    deltaOffsets: [3.0, 2.0, 1.0, 0.5, 0.25, 0, -0.25, -0.5, -1.0, -2.0, -3.0],
    thresholdGuideline: 1.0,
  },
  DOGE: {
    id: 'DOGE',
    symbol: 'Ð',
    label: 'DOGE',
    name: 'Dogecoin',
    color: '#e1b303',
    bgGrad: 'from-[#e1b303] to-[#c2a633]',
    decimals: 6,
    minSpotDiff: 0.0005,
    defaultBuffer: 0.002,
    minBuffer: 0.0005,
    deltaOffsets: [0.004, 0.002, 0.001, 0.0005, 0, -0.0005, -0.001, -0.002, -0.004],
    thresholdGuideline: 0.001,
  },
};

export const CRYPTO_ASSET_LIST: CryptoAssetMeta[] = Object.values(CRYPTO_ASSETS);

export function getAssetMeta(asset?: string): CryptoAssetMeta {
  if (asset && asset in CRYPTO_ASSETS) {
    return CRYPTO_ASSETS[asset as CryptoAsset];
  }
  return CRYPTO_ASSETS.BTC;
}

export function formatAssetPrice(price: number, asset?: string): string {
  const meta = getAssetMeta(asset);
  return price.toLocaleString('en-US', {
    minimumFractionDigits: meta.decimals >= 4 ? 4 : 2,
    maximumFractionDigits: meta.decimals,
  });
}

export function formatAssetDelta(delta: number, asset?: string): string {
  const meta = getAssetMeta(asset);
  const sign = delta >= 0 ? '+' : '-';
  const absVal = Math.abs(delta);
  const formatted = absVal.toLocaleString('en-US', {
    minimumFractionDigits: meta.decimals >= 4 ? 4 : (absVal < 1 ? 2 : (meta.decimals === 2 && absVal % 1 !== 0 ? 2 : 0)),
    maximumFractionDigits: meta.decimals,
  });
  return `${sign} $${formatted}`;
}
