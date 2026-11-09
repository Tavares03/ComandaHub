"""Integracao real com o iFood (Merchant API, app centralizado).

- client.py: chamadas HTTP (token, lojas, eventos, pedidos e acoes de status)
- mapper.py: converte o pedido do iFood no formato interno
- service.py: processa eventos, cria pedidos, aplica e envia mudancas de status
- poller.py: polling em segundo plano (mantem a loja aberta no iFood)
"""
