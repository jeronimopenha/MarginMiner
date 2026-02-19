class Parse:
    @staticmethod
    def float(le: str):
        txt = le.strip()

        if not txt:
            return None

        txt = txt.replace("R$", "").strip()

        txt = txt.replace(",", "")

        try:
            return float(txt)
        except ValueError:
            return None

    @staticmethod
    def percent(le: str):
        txt = le.strip()

        if not txt:
            return None

        txt = txt.replace("%", "").strip()

        txt = txt.replace(",", "")

        try:
            return float(txt)
        except ValueError:
            return None
