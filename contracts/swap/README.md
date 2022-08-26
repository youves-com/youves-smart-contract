# Flat CFMM

CFMM between two tokens (FA1.2 / FA2 each) using the isoutility curve U(x,y) = (x+y)^8 - (x-y)^8
This curve has the benefit of being extremely flat around x = y, at which point dx U / dy U = -1.
This makes it suitable to create a CFMM between two assets which ought to be pegged to one another.

Based on the generic cfmm in the ctez repo which is itself based on dexter v2.

Barely tested!

## The curve

![Curve showing the constant product curve, the constant sum curve, and the compromise](https://user-images.githubusercontent.com/1591742/130374091-5c447f97-8bb1-407c-b97d-eb463fdd8666.png)

To give some sense, when the two assets are held in equal amounts, 78% of the pool can be bought for a slippage of less than 5%.

![Slippage for constant product, sum, and the compromise](https://user-images.githubusercontent.com/1591742/130378341-f34f2a06-e860-4ec0-997f-0812990746f6.png)

## Proof for the flat curve

The curve is given by the implict equation

$$U(x,y) = (x+y)^8 - (x-y)^8 = k$$

When swapping a quantity $\delta x$ we search a quantity $\delta y$ such that $U(x + \delta x, y - \delta y) = U(x, y)$. We approximate the solution $\delta y$ using Newton's method:

$$\delta^{(k+1)} y = \delta^{(k)} y + \frac{U(x + \delta x, y - \delta^{(k)} y) - U(x, y)}{U_y(x+\delta x, y - \delta^{(k)} y)}$$

We note that $\delta^{(k+1)}y$ is the intersection between the tangent line to the curve $$u(\delta^{(k)} y) = U(x + \delta x, y - \delta^{(k)} y)$$ at point $(\delta^{(k)} y, U(x + \delta x, y - \delta^{(k)} y)$.

and the line $$u(\delta^{(k)} y) = U(x,y)$$

While we are looking for the value $\delta y$ at the intersection between

$u(\delta y) = U(x + \delta x, y - \delta y)$ and $u(\delta y) = U(x, y)$.

Note that $U(x,\delta x, y - \delta y)$ is convex in $\delta y$. Indeed its second derivative with respect to $\delta y$ is:

$$56((x+\delta x+y-\delta y)^6 - (x+\delta x-(y-\delta y))^6) \ge 0$$

therefore we have:

$$(\delta y - \delta^{(k+1)} y)(\delta y - \delta^{(k)} y) \ge 0$$

for all $k$.

($\delta^{(k)} y$ stays on the same side of $\delta y$ it starts from).

Since we start with $\delta^{(0)} k = 0 \le \delta y$ then for all k, $\delta^{(k)} y \le \delta y$

A picture to illustrate

![](https://i.imgur.com/gKFvSgx.png)

In the codebase, we compute the newton update *exactly* in the rational numbers, and then round the fraction *down* to the nearest integer. This ensures that we only produce underestimates of $\delta y$.

## Compilation
For compilation create a new folder called **out**. In this folder you will store the compiled michelson code.

### Liquidity Pool
To compile the liquidity pool run the following command:
```
docker run --rm -v "$PWD":"$PWD" -w "$PWD" ligolang/ligo:0.34.0 compile contract liquidity_pool.mligo > ./out/liquidity_pool.tz
```

### Flat CFMM
The flat CFMM supports 2 types of cash tokens (FA1.2 and FA2). Before compiling the flat CFMM contract you must select
one of the flags: **CASH_IS_FA12** or **CASH_IS_FA2** in the **flat_cfmm.mligo** file.

To compile a flat CFMM having the cash as a FA1.2 token, select the CASH_IS_FA12 flag and run the following command:
```
docker run --rm -v "$PWD":"$PWD" -w "$PWD" ligolang/ligo:0.34.0 compile contract flat_cfmm.mligo > ./out/fa12_flat_cfmm.tz
```

To compile a flat CFMM having the cash as a FA2 token, select the CASH_IS_FA2 flag and run the following command:
```
docker run --rm -v "$PWD":"$PWD" -w "$PWD" ligolang/ligo:0.34.0 compile contract flat_cfmm.mligo > ./out/fa2_flat_cfmm.tz
```

## Deployment

### Requirements
To deploy the contract you need to install pytezos.

To install pytezos, run the following commands (you need to have at least python version 3.5 installed):
```
$ pip install wheel setuptools pkginfo cryptography
$ pip install pytezos
```
**Note**: For pytezos to work, you need to install cryptographic packages before installing the library/building the project.

**Linux**
```
$ sudo apt install libsodium-dev libsecp256k1-dev libgmp-dev
```

**MacOS**
```
$ brew tap cuber/homebrew-libsecp256k1
$ brew install libsodium libsecp256k1 gmp
```

### Deployment
Before deployment, select the correct config and run the following command:

```
$ python3 deployments/deploy_fa2_flat_cfmm.py
```
or
```
$ python3 deployments/deploy_fa12_flat_cfmm.py
```
depending on what type of token the cash in the CFMM is.

If you need to change the initial state of the storage, check the appropiate config file and update it accordingly before deploying.
