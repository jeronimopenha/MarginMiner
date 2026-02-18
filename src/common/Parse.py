class Parse:
    @staticmethod
    def float(le: str):
        txt = le.strip()

        if not txt:
            return None

        # remove R$
        txt = txt.replace("R$", "").strip()

        # suporta vírgula brasileira
        txt = txt.replace(",", ".")

        try:
            return float(txt)
        except ValueError:
            return None

    @staticmethod
    def percent(le: str):
        txt = le.strip()

        if not txt:
            return None

        # remove %
        txt = txt.replace("%", "").strip()

        # suporta vírgula brasileira
        txt = txt.replace(",", ".")

        try:
            return float(txt)
        except ValueError:
            return None
