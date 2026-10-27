"""
Zien Crypto — Liquid Crypto Pairs Catalogue and Default Configurations
"""

from typing import Dict, Any

# Top 30 Liquid Pairs on Binance (Spot & Futures) with metadata
CRYPTO_CATALOGUE: Dict[str, Dict[str, Any]] = {
    "BTCUSDT": {"name": "Bitcoin", "base": "BTC", "quote": "USDT", "sector": "Layer 1 / Store of Value", "precision": 2, "futures": True},
    "ETHUSDT": {"name": "Ethereum", "base": "ETH", "quote": "USDT", "sector": "Smart Contracts L1", "precision": 2, "futures": True},
    "SOLUSDT": {"name": "Solana", "base": "SOL", "quote": "USDT", "sector": "High-Speed L1", "precision": 2, "futures": True},
    "BNBUSDT": {"name": "BNB", "base": "BNB", "quote": "USDT", "sector": "Exchange / Ecosystem", "precision": 2, "futures": True},
    "XRPUSDT": {"name": "XRP", "base": "XRP", "quote": "USDT", "sector": "Cross-Border Payments", "precision": 4, "futures": True},
    "DOGEUSDT": {"name": "Dogecoin", "base": "DOGE", "quote": "USDT", "sector": "Meme / Pow", "precision": 5, "futures": True},
    "ADAUSDT": {"name": "Cardano", "base": "ADA", "quote": "USDT", "sector": "Smart Contracts L1", "precision": 4, "futures": True},
    "AVAXUSDT": {"name": "Avalanche", "base": "AVAX", "quote": "USDT", "sector": "Smart Contracts L1", "precision": 2, "futures": True},
    "LINKUSDT": {"name": "Chainlink", "base": "LINK", "quote": "USDT", "sector": "Oracle / Infra", "precision": 3, "futures": True},
    "SUIUSDT": {"name": "Sui", "base": "SUI", "quote": "USDT", "sector": "High-Speed L1", "precision": 4, "futures": True},
    "NEARUSDT": {"name": "NEAR Protocol", "base": "NEAR", "quote": "USDT", "sector": "AI / Sharded L1", "precision": 3, "futures": True},
    "DOTUSDT": {"name": "Polkadot", "base": "DOT", "quote": "USDT", "sector": "Interoperability", "precision": 3, "futures": True},
    "LTCUSDT": {"name": "Litecoin", "base": "LTC", "quote": "USDT", "sector": "Payments / PoW", "precision": 2, "futures": True},
    "BCHUSDT": {"name": "Bitcoin Cash", "base": "BCH", "quote": "USDT", "sector": "Payments / PoW", "precision": 2, "futures": True},
    "UNIUSDT": {"name": "Uniswap", "base": "UNI", "quote": "USDT", "sector": "DeFi / DEX", "precision": 3, "futures": True},
    "APTUSDT": {"name": "Aptos", "base": "APT", "quote": "USDT", "sector": "Move L1", "precision": 3, "futures": True},
    "FETUSDT": {"name": "Artificial Superintelligence", "base": "FET", "quote": "USDT", "sector": "AI / Decentralized Compute", "precision": 4, "futures": True},
    "TIAUSDT": {"name": "Celestia", "base": "TIA", "quote": "USDT", "sector": "Modular DA", "precision": 3, "futures": True},
    "ARBUSDT": {"name": "Arbitrum", "base": "ARB", "quote": "USDT", "sector": "Ethereum L2", "precision": 4, "futures": True},
    "OPUSDT": {"name": "Optimism", "base": "OP", "quote": "USDT", "sector": "Ethereum L2", "precision": 4, "futures": True},
    "INJUSDT": {"name": "Injective", "base": "INJ", "quote": "USDT", "sector": "DeFi L1", "precision": 3, "futures": True},
    "RENDERUSDT": {"name": "Render", "base": "RENDER", "quote": "USDT", "sector": "DePIN / AI Compute", "precision": 3, "futures": True},
    "PEPEUSDT": {"name": "Pepe", "base": "PEPE", "quote": "USDT", "sector": "Meme", "precision": 8, "futures": True},
    "SHIBUSDT": {"name": "Shiba Inu", "base": "SHIB", "quote": "USDT", "sector": "Meme", "precision": 8, "futures": True},
    "WIFUSDT": {"name": "dogwifhat", "base": "WIF", "quote": "USDT", "sector": "Meme", "precision": 4, "futures": True},
    "STXUSDT": {"name": "Stacks", "base": "STX", "quote": "USDT", "sector": "Bitcoin L2", "precision": 4, "futures": True},
    "KASUSDT": {"name": "Kaspa", "base": "KAS", "quote": "USDT", "sector": "BlockDAG L1", "precision": 5, "futures": True},
    "FILUSDT": {"name": "Filecoin", "base": "FIL", "quote": "USDT", "sector": "DePIN / Storage", "precision": 3, "futures": True},
    "AAVEUSDT": {"name": "Aave", "base": "AAVE", "quote": "USDT", "sector": "DeFi Lending", "precision": 2, "futures": True},
    "TAOUSDT": {"name": "Bittensor", "base": "TAO", "quote": "USDT", "sector": "Decentralized AI", "precision": 2, "futures": True},
}

DEFAULT_CRYPTO_CONFIG: Dict[str, Any] = {
    "monitored_symbols": list(CRYPTO_CATALOGUE.keys())[:15],
    "default_timeframe": 5,
    "fast_ema_period": 9,
    "slow_ema_period": 21,
    "rsi_period": 14,
    "atr_period": 14,
    "score_threshold": 65,
    "min_rr_ratio": 1.5,
    "cvd_window_bars": 30,
    "funding_extreme_rate": 0.0005,  # 0.05% per 8h considered heavy skew
}
