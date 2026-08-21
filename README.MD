# Balanceador de carga - MC714

Implementação do primeiro trabalho da disciplina MC714 - Sistemas Distribuídos
da UNICAMP. O projeto usa Python e SimPy para construir, em pequenos módulos
funcionais, uma simulação de balanceamento de carga entre três servidores.

## Estado atual

Neste marco, a base do domínio e o processamento de um servidor já estão
implementados:

- ambiente de eventos discretos com SimPy;
- configuração imutável de uma rodada, com valores padrão e validação de
  políticas, servidores, rajadas, tempos, Hurst e semente;
- entidade `Request`, com identificadores, instante de chegada e transições
  validadas de atribuição, início de serviço e conclusão;
- cálculo do tempo em fila e do tempo de resposta de uma requisição;
- servidor com capacidade e tempo de serviço configuráveis, usando
  `simpy.Resource` e fila FIFO;
- valores padrão do servidor compatíveis com o trabalho: 15 requisições
  simultâneas e serviço constante de 0,05 unidade de tempo;
- monitoramento local de requisições ativas, fila, conclusões e máximos
  observados;
- histórico imutável do estado do servidor nos eventos de recebimento, início
  e conclusão do serviço;
- coletor central com eventos imutáveis de chegada, roteamento, início e
  conclusão do serviço, incluindo o estado básico do servidor quando
  disponível;
- resumo imutável de uma rodada com chegadas, conclusões, pendências,
  throughput, tempo médio em fila e tempo médio de resposta;
- validação das invariantes de topologia, capacidade, ciclo de vida das
  requisições, janela de medição e conservação do sistema;
- testes unitários das validações, do ciclo de vida da requisição, do limite de
  capacidade, da ordem FIFO e do monitoramento.

O caso de 16 requisições simultâneas está coberto pelos testes: 15 iniciam em
`t = 0` e a última inicia em `t = 0,05`.

Ainda não há uma simulação completa com três servidores. Criação da rodada a
partir da configuração, balanceador, políticas, tráfego Pareto, integração do
coletor, logs configuráveis, experimentos, modelo analítico, CSVs e gráficos
serão adicionados em etapas posteriores, conforme o
[plano de implementação](PLANO_IMPLEMENTACAO.md).

## Componentes implementados

| Componente | Responsabilidade |
| --- | --- |
| `SimulationConfig` | Mantém e valida os parâmetros imutáveis de uma rodada. |
| `MetricEvent` | Representa um evento observado pelo coletor. |
| `MetricsCollector` | Preserva eventos e calcula as métricas de uma rodada. |
| `RunMetrics` | Representa o resumo imutável de uma rodada. |
| `validate_simulation_invariants` | Valida configuração, servidores e eventos. |
| `Request` | Mantém o ciclo de vida e os tempos de uma requisição. |
| `Server` | Processa requisições concorrentemente e enfileira o excesso. |
| `ServerState` | Representa uma fotografia imutável do estado do servidor. |

O `Server` exige que a requisição já esteja atribuída ao seu identificador.
Essa atribuição será responsabilidade do balanceador quando ele for
implementado.

## Métricas da rodada

`MetricsCollector.calculate_run_metrics(horizon)` calcula as métricas usando
somente os eventos da janela informada. Chegadas devem ocorrer antes do
horizonte; conclusões exatamente no horizonte são contabilizadas.

```text
throughput = requisições concluídas / horizonte
tempo em fila = início do serviço - chegada
tempo de resposta = conclusão - chegada
```

As médias são `None` quando ainda não existe nenhuma observação aplicável.

## Invariantes da simulação

Ao final de uma rodada,
`validate_simulation_invariants(config, servers, collector)` verifica:

- quantidade, identificadores, capacidade e tempo de serviço dos servidores;
- uso do mesmo ambiente SimPy pelos servidores e pelo coletor;
- limites de requisições ativas e tamanho não negativo das filas;
- sequência `arrival`, `routing`, `service_started`, `service_completed`;
- permanência da requisição no mesmo servidor durante o atendimento;
- ausência de chegadas no horizonte ou depois dele;
- conservação `chegadas = concluídas + ativas + aguardando`.

Uma violação lança `SimulationInvariantError`. Eventos de conclusão posteriores
ao horizonte, gerados por uma eventual fase de drenagem, não alteram a
validação da janela oficial.

## Requisitos

- Python 3.11 ou mais recente;
- `pip`.

## Preparação do ambiente

### Linux

```bash
python3 -m venv venv
source venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e ".[dev]"
```

### Windows PowerShell

```powershell
py -3 -m venv venv
venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -e ".[dev]"
```

## Exemplo dos componentes atuais

```python
import simpy

from load_balancer_sim import Request, Server, SimulationConfig

config = SimulationConfig()
environment = simpy.Environment()
server = Server(
    environment,
    server_id=0,
    capacity=config.server_capacity,
    service_time=config.service_time,
)
request = Request(id=0, burst_id=0, arrival_time=environment.now)

request.assign_to(server.id)
environment.process(server.handle(request))
environment.run()

print(request.response_time)   # 0.05
print(server.completed_count)  # 1
```

## Verificação

Com o ambiente virtual ativado, execute toda a suíte de testes:

```bash
pytest
```

Os testes ficam em `tests/` e não dependem de tempo real: toda a passagem do
tempo ocorre no relógio simulado do SimPy.

## Estrutura atual

```text
src/load_balancer_sim/
├── __init__.py
├── config.py
├── invariants.py
├── metrics.py
├── request.py
└── server.py

tests/
├── test_config.py
├── test_environment.py
├── test_invariants.py
├── test_metrics.py
├── test_request.py
└── test_server.py
```

O roteiro completo, incluindo a divisão de responsabilidades da dupla, está em
[PLANO_IMPLEMENTACAO.md](PLANO_IMPLEMENTACAO.md).
