# Youves DAO

Youves DAO is the implementation of the DAO for the Youves platform. The DAO is used to govern [YOU tokens](https://app.youves.com).

Youves DAO allows YOU holders to use their stakes (held in the unified staking contract) to vote on a proposal.
If the vote passes, then the proposal is moved into a timelock.

The DAO takes a lambda and will execute the code in the lambda if the vote passes.


## Governance Flow

A proposal goes through several phases in Murmuration:
1. A user submits a **proposal**, which becomes a **poll**.
2. A voting period occurs, where voters vote on the **poll**.
3. If the poll passes, it is moved to the **timelock**.
4. After a timelock period, the proposal may be executed by the user who submitted it. 
5. After a cancellation period, the proposal may be cancelled by any user. 

In addition, the DAO have a break glass contract that may help to expedite proposals, by reducing
the voting & waiting time.

## Design Rational

Youves takes an opinionated approach to governance and for a period of time the
glass breaker contract can still veto a proposal even if it met the majority to be
executed. This is made to make sure the community understands how the DAO works
and what are the necessary knowledge steps in order to make Youves a sucessfull DAO.

## Voting/Voting Contract
Users can vote on a proposal using their staked YOUs in the unified staking contract. Therefore, in
order to vote, users must first stake their YOUs in the unified staking contract and use the entire
stake for a vote.

After a user has voted, their stake is temporarily transfered to the DAO such that double voting is
avoided and rewards can still be accrued on the stake.

### Vote weight
To avoid late voting, we use the stake weight as voting power because this represents the weight as
moment of time t = 0, so all votes will be time independent.

### End vote
At the end of the voting period, all votes weights are counted in and they are converted back to YOU
values (multiplied by the disc_factor in the unified staking). This conversion will always preserve the
percentages of the vote weight, therefore if at the end of voting, the weights are distributed like so:
60% Yes, 25% No, 15% Abstain, after the conversion, these percentage will remain the same with the caveat
of fixed floating point arithmetic errors.

After the conversion, there is a check to see if the quorum is met, and the proposal either passes and
it is moved into the timelock or it is canceled.

## Timelock
After a proposal passes it is move into the timelock. During this period, a break glass contract can
veto the proposal (this is just a preliminary precaution that Youves is taking in order to ensure that
the community is using the DAO correctly). The break glass contract can only intervine between the time
a proposal is added to the timelock and the timelock is executed by the proposer.

### Execution
After a certain amount of time (counted in blocks), the propers and only the proposer can execute the proposal.

### Cancelation
After a cancellation period, the proposal may be cancelled by any user, in order to ensure that the timelock is
open for future proposals. The proposer will always have the oportunity to execute the timelock before it can
be canceled.

## Spam Prevention

Youves only allows a single poll to be underway at a time. As such, users may front run polls as a denial of service attack to prevent real proposals from being put forth. 

To prevent this attack, Youves escrows a number of tez/tokens from the user when they make a proposal. If the proposal does not achieve a minimum number of 'Yes' votes, the escrowed tokens are confiscated, otherwise they are returned to the user at the conclusion of a poll. 

This also serves as a strong incentive for users to coordinate their proposals off chain and achieve broad consensus before submitting a proposal, which serves to limit the number of controversial or failing proposals that are actually put up for a vote.

## Execution Safety

Only the submitter of a proposal may ultimately execute the proposal. This is a safety measure as the author of the proposal is likely to understand best the effects of the proposal. If conditions change while the proposal is timelocked, it may be advantageous to ultimately not execute the proposal. By giving the author a priviledged role, we limit the chance of a proposal being executed in a disadvantageous context. 

In the case that the author loses their keys or is unavailable, any user can cancel the timelock after a cancellation period. This discards the propsoal and frees the timelock for a future proposal. 

## Flash Loan Resistance

The users will transfer their stake to the DAO after they vote and will be kept locked by the DAO contract
until the end of the voting period. This prevents a flash loan voting attack and double counting the votes.
