import smartpy as sp


class TokenVariant:
    def get_type():
        return sp.TVariant(
            fa2=sp.TRecord(contract=sp.TAddress, token_id=sp.TNat).layout(
                ("contract", "token_id")
            ),
            fa1=sp.TAddress,
            tez=sp.TUnit,
        )


class Assets:
    def get_single_type():
        return sp.TRecord(token=TokenVariant.get_type(), amount=sp.TNat).layout(
            ("token", "amount")
        )

    def get_mapped_type():
        return sp.TMap(TokenVariant.get_type(), sp.TNat)

    def get_list_type():
        return sp.TList(Assets.get_single_type())
