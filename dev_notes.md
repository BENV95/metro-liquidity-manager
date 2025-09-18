# Metro Liquidity Manager Development Notes

## Trading

The main aim is to create trading functionality that trades the rewards in **$METRO** (Reward token) for **$S** (Native token) or **$USDC**.

There are several decentralised exchnages that offer trading of these assets, as well as several trading strategies that could be deployed.

### Exchnage Comparison

| Exchange   | Contract Name | Contract Address | Swap Function              | Token Approval |
|------------|---------------|------------------|----------------------------|----------------|
| Metropolis | LBRouter      | ```0x67803fe6d76409640efDC9b7ABcD2c6c2E7cBa48```              | ```swapExactTokensForNATIVE``` | Yes           |
| Metropolis | LBRouter      | ```0x67803fe6d76409640efDC9b7ABcD2c6c2E7cBa48```              | ```swapExactTokensForTokens``` | Yes           |
| Shadow     | TBD           | TBD              | TBD                        | TBD           |
| SwapX      | TBD           | TBD              | TBD                        | TBD           |

### Metropolis
Metropolis is preferential for swapping the rewards token because it has the deepest ```$METRO``` liquidity pools.

#### Example LBRouter contract execution ABI for swap to native tokens:
```json
{
  "func": "swapExactTokensForNATIVE",
  "params": [
    82586077623973899628,
    // amountIn (uint256) - Input token amount in wei
    23247052544632128573,
    // amountOutMinNATIVE (uint256) - Minimum native tokens expected in wei
    [
      [0],
      // pairBinSteps (uint256[]) - Bin step for the pair
      [0],
      // versions (enum ILBRouter.Version[]) - Version for the pair
      [
        "0x71E99522EaD5E21CF57F1f542Dc4ad2E841F7321",
        // METRO token (input)
        "0x039e2fB66102314Ce7b64Ce5Ce3E5183bc94aD38"
        // Intermediate token before native
      ]
      // tokenPath (contract IERC20[]) - Token addresses in swap path
    ],
    // path (struct ILBRouter.Path)
    "0xc74A76Fa975a1467f1B90612AfacA4a3419a4e31",
    // to (address payable) - Recipient address
    1758235261
    // deadline (uint256) - Unix timestamp deadline
  ]
}
```
#### Example contract ABI for swap to any tokens:
```json
{
  "func": "swapExactTokensForTokens",
  "params": [
    82586077623973899628,
    // amountIn (uint256) - Input token amount in wei
    7205872,
    // amountOutMin (uint256) - Minimum output tokens expected
    [
        // path (struct ILBRouter.Path)
      [0, 4],
      // pairBinSteps (uint256[]) - Bin steps for each pair
      [0, 2],
      // versions (enum ILBRouter.Version[]) - Version for each pair
      [
        // tokenPath (contract IERC20[]) - Token addresses in swap path
        "0x71E99522EaD5E21CF57F1f542Dc4ad2E841F7321",
        // METRO token
        "0x039e2fB66102314Ce7b64Ce5Ce3E5183bc94aD38",
        // Intermediate token
        "0x29219dd400f2Bf60E5a23d13Be72B486D4038894"
        // Output token
      ]
    ],
    "0xc74A76Fa975a1467f1B90612AfacA4a3419a4e31",
    // to (address) - Recipient address
    1758236823
    // deadline (uint256) - Unix timestamp deadline
  ]
}
```