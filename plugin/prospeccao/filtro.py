# Funções puras. None = não medido; 0 é valor medido, nunca ausente.


def classificar(lead):
    if (lead.get("site_url") or "").strip():  # vazio, só espaços ou None = ausente
        tem_site = True
    elif lead.get("verificado_site") is True:  # só True explícito: verificação confirmou ausência
        tem_site = False
    else:
        tem_site = None
    return {**lead, "tem_site": tem_site}


def filtrar(leads, criterios):
    def aceita(lead):
        nota_min = criterios.get("nota_min")
        if nota_min is not None and (lead.get("nota") is None or lead["nota"] < nota_min):
            return False
        av_min = criterios.get("avaliacoes_min")
        if av_min is not None and (lead.get("avaliacoes") is None or lead["avaliacoes"] < av_min):
            return False
        if criterios.get("sem_site") and classificar(lead)["tem_site"] is not False:
            return False  # tem_site None (não sabido) não passa no critério sem_site
        return True

    return [lead for lead in leads if aceita(lead)]
