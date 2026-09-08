# Balanceador de carga - MC714

Simulador de um balanceador de carga para três servidores, desenvolvido em
Python e SimPy para o Trabalho 1 de MC714 - Sistemas Distribuídos da UNICAMP.

O enunciado vigente é `MC714_enunciado.pdf`. Em pontos de divergência, ele
substitui a versão antiga `MC714_2s2026.pdf`. O roteiro atualizado está em
[PLANO_IMPLEMENTACAO.md](PLANO_IMPLEMENTACAO.md).

## Objetivo vigente

O sistema final terá:

- chegadas Poisson;
- 3 servidores homogêneos com uma unidade de processamento cada;
- filas FCFS ilimitadas;
- tempos de serviço exponenciais com `mu=1` e média 1;
- políticas Aleatória, Round Robin e Fila Mais Curta;
- execuções de 5000 unidades, descartando as primeiras 500 como warm-up;
- métricas de vazão, resposta, número médio no sistema e utilização;
- comparação com o modelo analítico `M/M/1` da política Aleatória.

## Estado atual

Já estão implementados:

- `SimulationConfig` imutável e validada;
- `Request` e seu ciclo de vida;
- `Server` com uma unidade de processamento, fila FIFO, serviço exponencial
  reproduzível, histórico de estados e callbacks públicos de serviço;
- configuração vigente com `service_rate=1`, horizonte 5000 e warm-up 500;
- `MetricsCollector`, `RunMetrics` e eventos imutáveis;
- invariantes de topologia, capacidade, eventos e conservação;
- logs estruturados de configuração, eventos e resumo;
- `LoadBalancer`;
- políticas Aleatória, Round Robin e Fila Mais Curta em módulo próprio, com
  sementes reproduzíveis e desempates aleatórios;
- gerador de chegadas Poisson reproduzível;
- testes unitários e teste de integração do ciclo completo de uma requisição;
- notebooks de configuração e integração.

Em 8 de setembro de 2026, a suíte possui **168 testes aprovados**.

## Alinhamentos ainda necessários

Ainda faltam:

- aplicação do warm-up e cálculo temporal de `E[N]` e utilização por servidor;
- executor completo de uma rodada;
- executor das 150 rodadas estáveis;
- modelo analítico `M/M/1`;
- experimento instável com `lambda=3,3`;
- intervalos de confiança, CSVs, gráficos e CLI.

O gerador Poisson já está alinhado ao novo enunciado. Pareto Limitada, Hurst e
rajadas de 30 a 120 não fazem mais parte dos requisitos vigentes.

## Componentes

| Componente | Responsabilidade |
| --- | --- |
| `SimulationConfig` | Configura capacidade 1, `mu=1`, horizonte 5000 e warm-up 500. |
| `Request` | Mantém IDs, chegada, atribuição, início, conclusão e tempos derivados. |
| `Server` | Sorteia serviços exponenciais, mantém fila FIFO e publica callbacks de início e conclusão. |
| `ServerState` | Fotografia imutável do estado de um servidor. |
| `LoadBalancer` | Valida servidores e requisições, seleciona um servidor e inicia o atendimento. |
| `RandomPolicy` | Escolhe um servidor pseudoaleatoriamente. |
| `RoundRobinPolicy` | Distribui requisições ciclicamente. |
| `ShortestQueuePolicy` | Escolhe a menor ocupação e desempata pseudoaleatoriamente. |
| `PoissonTrafficGenerator` | Produz chegadas Poisson no ambiente SimPy. |
| `MetricsCollector` | Preserva eventos e calcula as métricas atualmente disponíveis. |
| `RunMetrics` | Resumo imutável de uma rodada. |
| `SimulationLogger` | Emite configuração, eventos e resumo. |
| `validate_simulation_invariants` | Valida topologia, ciclos de vida e conservação. |

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

## Testes

Com o ambiente virtual ativado:

```bash
pytest
```

Os testes usam somente o relógio simulado do SimPy e não dependem de espera em
tempo real.

## Tempo de serviço

Por padrão, cada servidor sorteia uma duração exponencial de média
`1/service_rate`. A semente torna a sequência reproduzível:

```python
server = Server(environment, server_id=0, service_rate=1.0, seed=123)
```

Testes e futuros traços de carga podem fornecer um sampler próprio:

```python
server = Server(
    environment,
    server_id=0,
    service_time_sampler=lambda request: 0.05,
)
```

Essa injeção permite usar durações conhecidas nos testes e, futuramente,
reutilizar a mesma demanda de serviço nas três políticas.

## Estrutura atual

```text
src/load_balancer_sim/
├── __init__.py
├── config.py
├── invariants.py
├── load_balancer.py
├── logs.py
├── metrics.py
├── policies.py
├── request.py
├── server.py
└── traffic.py

tests/
├── test_config.py
├── test_environment.py
├── test_invariants.py
├── test_load_balancer.py
├── test_logs.py
├── test_metrics.py
├── test_policies.py
├── test_request.py
├── test_server.py
└── test_traffic.py
```

Os notebooks em `notebooks/` são materiais auxiliares. O fluxo definitivo da
simulação deve residir nos módulos do pacote, sem acessar atributos privados.

## Próximo commit técnico

O próximo marco é implementar as métricas temporais: número médio de
requisições no sistema, utilização individual dos servidores e recorte correto
da janela de medição após o warm-up.
