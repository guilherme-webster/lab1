# Plano de implementação - Trabalho 1 de MC714

Este plano segue o enunciado atualizado `MC714_enunciado.pdf`. Quando houver
divergência com `MC714_2s2026.pdf`, o enunciado atualizado tem precedência.

> Prazo: **22 de setembro de 2026**. O trabalho deve ser desenvolvido em dupla
> e entregue como um relatório IEEE de no máximo 4 páginas e um arquivo
> compactado com o código-fonte.

## 1. Especificação vigente

### Sistema

- 3 servidores homogêneos;
- uma única unidade de processamento por servidor;
- uma fila FCFS ilimitada por servidor;
- chegadas segundo um processo de Poisson de taxa `lambda`;
- intervalos entre chegadas exponenciais com média `1/lambda`;
- tempos de serviço exponenciais com média `1/mu`;
- `mu = 1,0` requisição por unidade de tempo, portanto `E[S] = 1`;
- balanceador instantâneo, sem tempo próprio de processamento.

Cada servidor é, sob a política aleatória, uma fila `M/M/1`. O
`simpy.Resource` de cada servidor deve ter `capacity=1`. A fila do recurso pode
permanecer ilimitada.

### Políticas obrigatórias

1. **Aleatória:** escolhe cada servidor com probabilidade `1/3`, de maneira
   independente para cada requisição.
2. **Round Robin:** produz a sequência cíclica `1, 2, 3, 1, 2, 3, ...`.
3. **Fila Mais Curta:** minimiza o número total de requisições no servidor,
   isto é, `active_count + waiting_count`; empates são resolvidos
   aleatoriamente.

### Experimentos estáveis

- taxas `lambda` em `{0,6; 1,2; 1,8; 2,4; 2,7}`;
- as 3 políticas para cada taxa: 15 configurações no total;
- 5000 unidades de tempo por execução;
- descarte das primeiras 500 unidades como warm-up;
- janela oficial de medição: `[500, 5000)`, com duração 4500;
- 10 réplicas de cada configuração, com sementes diferentes;
- média e intervalo de confiança de 95% das 10 réplicas.

O conjunto principal possui:

```text
5 taxas x 3 políticas x 10 réplicas = 150 execuções
```

### Experimento instável

Executar também `lambda = 3,3` e observar o número de requisições no sistema ao
longo do tempo. Como a capacidade total é `3*mu = 3`, a carga excedente é:

```text
lambda - 3*mu = 3,3 - 3 = 0,3 requisição por unidade de tempo
```

A aproximação fluida a comparar com a simulação é:

```text
N(t) ~= N(0) + (lambda - 3*mu)*t
```

### Métricas obrigatórias

- vazão do sistema `X`;
- tempo médio de resposta `E[R]`;
- número médio de requisições no sistema `E[N]`;
- utilização individual `U_i` de cada servidor.

`E[N]` deve ser calculado pela área sob a curva de ocupação dividida pela
duração da janela, e não pela média observada apenas nos instantes de chegada.

### Modelagem analítica

O modelo analítico completo é obrigatório apenas para a política Aleatória.
Round Robin e Fila Mais Curta são avaliadas por simulação e comparadas com a
referência analítica da política Aleatória.

### Ponto extra opcional

Escolher somente uma alternativa:

- **buffer finito:** `K` em `{5, 10, 20}`, fila `M/M/1/K`, probabilidade de
  perda `P_perda = p_K` e vazão efetiva `X = lambda*(1-P_perda)`;
- **servidores heterogêneos:** `mu_1=1,5`, `mu_2=1,0`, `mu_3=0,5`, com pesos de
  roteamento proporcionais a `mu_i`.

O ponto extra só deve começar depois que todos os requisitos obrigatórios
estiverem validados.

## 2. Principais mudanças em relação ao enunciado antigo

| Aspecto | Enunciado antigo | Enunciado vigente |
| --- | --- | --- |
| Chegadas | Pareto Limitada, Hurst 0,8 e rajadas | Poisson com taxa `lambda` |
| Serviço | Constante em 0,05 | Exponencial com média 1 (`mu=1`) |
| Concorrência | 15 por servidor | 1 por servidor |
| Fila | Capacidade associada a 15 processamentos | FCFS ilimitada |
| Horizonte | 200 | 5000, descartando as primeiras 500 |
| Cenários | Rajadas 30, 60, 90 e 120 | `lambda` 0,6; 1,2; 1,8; 2,4; 2,7 |
| Repetições principais | 120 execuções | 150 execuções |
| Métricas | Vazão e resposta | Vazão, resposta, `E[N]` e `U_i` |
| Modelo analítico | Divisão justa genérica, `M/M/15` sugerido | Aleatória, decomposição Poisson e três `M/M/1` |
| Sobrecarga | Não especificada separadamente | Experimento adicional com `lambda=3,3` |

Consequentemente, Pareto, Hurst, rajadas, capacidade 15, serviço constante de
0,05 e modelo `M/M/15` não fazem mais parte do caminho obrigatório.

## 3. Estado atual do repositório

### Já implementado

- pacote Python instalável com SimPy e pytest;
- `SimulationConfig` imutável com capacidade 1, `mu=1`, horizonte 5000 e
  warm-up 500;
- entidade `Request` com ciclo de vida e tempos derivados;
- `Server` baseado em `simpy.Resource`, fila FIFO, serviço exponencial
  reproduzível, sampler injetável e histórico de estados;
- `MetricsCollector`, `RunMetrics` e eventos imutáveis;
- invariantes de topologia, capacidade, ciclo de vida e conservação;
- logs estruturados em `INFO` e `DEBUG`;
- políticas Aleatória, Round Robin e Fila Mais Curta;
- `LoadBalancer` que atribui e encaminha requisições;
- gerador Poisson reproduzível e processo de chegada integrado ao SimPy;
- 134 testes automatizados aprovados em 8 de setembro de 2026;
- notebooks de integração e configuração.

### Desalinhamentos com o enunciado vigente

- as métricas ainda não aplicam o warm-up nem calculam `E[N]` por integração
  temporal ou `U_i`;
- Fila Mais Curta possui desempate determinístico pelo primeiro servidor, mas
  o novo enunciado exige desempate aleatório;
- a integração completa existe apenas em notebook e depende de monkey patch de
  membros privados do servidor;
- não existem `simulation.py`, executor das 150 rodadas, modelo analítico,
  exportação CSV, gráficos ou CLI;
- o notebook de configuração ainda contém trechos baseados no comportamento
  antigo.

## 4. Arquitetura alvo

```text
Traço de carga reproduzível
  - chegadas Poisson
  - duração exponencial por request
              |
              v
       LoadBalancer instantâneo
       - random / RR / shortest
          /        |        \
         v         v         v
      Server 0   Server 1   Server 2
      M/M/1      M/M/1      M/M/1
      FCFS        FCFS        FCFS
          \        |        /
           MetricsCollector
           - eventos
           - integrais de estado
           - métricas da réplica
                   |
             CSV + agregação
                   |
          teoria + gráficos + relatório
```

Para comparar políticas de forma justa, o traço de carga deve ser independente
da política. Para cada par `(lambda, replica)`, gerar previamente:

```text
(request_id, arrival_time, service_duration)
```

As três políticas recebem exatamente os mesmos instantes de chegada e as
mesmas demandas de serviço. A política Aleatória usa uma semente separada para
o roteamento.

## 5. Configuração alvo

Uma configuração de rodada deve convergir para algo semelhante a:

```python
SimulationConfig(
    policy="round_robin",
    server_count=3,
    server_capacity=1,
    service_rate=1.0,
    arrival_rate=1.8,
    horizon=5000.0,
    warmup=500.0,
    seed=12345,
)
```

`service_rate` representa `mu`. A duração de cada serviço é sorteada por:

```python
duration = rng.expovariate(service_rate)
```

Com `mu=1`, a média esperada é `1/mu = 1`. Para facilitar testes unitários, o
servidor pode receber uma função fornecedora de durações; testes de fila e
capacidade continuam usando durações determinísticas injetadas, enquanto as
simulações reais usam a exponencial.

## 6. Protocolo de medição

Adotar a janela semiaberta `[warmup, horizon) = [500, 5000)`. Registrar eventos
desde `t=0`, mas zerar ou recortar os acumuladores na fronteira do warm-up.

### Vazão

```text
X = conclusões ocorridas na janela / 4500
```

### Tempo de resposta

Usar as requisições concluídas durante a janela oficial e calcular:

```text
R_i = completion_time_i - arrival_time_i
E[R] = média dos R_i
```

Essa convenção deve ser aplicada igualmente às três políticas e declarada no
relatório.

### Número médio no sistema

Para cada intervalo entre mudanças de estado, acumular:

```text
area += (active_count + waiting_count) * delta_t
E[N] = soma das áreas dos três servidores / 4500
```

O trecho de um intervalo anterior ao warm-up ou posterior ao horizonte deve
ser recortado antes da integração.

### Utilização por servidor

Como cada servidor possui uma unidade de processamento:

```text
U_i = área sob active_count_i(t) / 4500
```

Assim, `0 <= U_i <= 1`.

### Intervalo de confiança

Para 10 réplicas, calcular a média, o desvio-padrão amostral e:

```text
IC95 = média +/- t_(0,975; 9) * s/sqrt(10)
```

## 7. Modelo analítico da política Aleatória

### Decomposição do processo de Poisson

Cada chegada escolhe um servidor com probabilidade `1/3`. Pelo teorema de
splitting de Poisson, cada servidor recebe um processo Poisson independente de
taxa:

```text
lambda_i = lambda/3
```

Cada servidor é uma fila `M/M/1` com `mu=1` e:

```text
rho = lambda_i/mu = lambda/3
```

A condição de estabilidade é:

```text
lambda < 3*mu = 3
```

### Fórmulas por servidor

Para `lambda < 3`:

```text
p_k = (1-rho)*rho^k
U_i = rho
E[N_i] = rho/(1-rho)
E[T_Q] = rho/(mu-lambda/3)
E[R] = 1/(mu-lambda/3)
```

### Fórmulas do sistema

```text
X = lambda
E[N] = 3*E[N_i]
E[N] = X*E[R]                 # Lei de Little
```

Com `mu=1`, os valores de referência são:

| lambda | rho = U_i | E[N_i] | E[T_Q] | E[R] | E[N] | X |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 0,6 | 0,2 | 0,25 | 0,25 | 1,25 | 0,75 | 0,6 |
| 1,2 | 0,4 | 0,6667 | 0,6667 | 1,6667 | 2,0 | 1,2 |
| 1,8 | 0,6 | 1,5 | 1,5 | 2,5 | 4,5 | 1,8 |
| 2,4 | 0,8 | 4,0 | 4,0 | 5,0 | 12,0 | 2,4 |
| 2,7 | 0,9 | 9,0 | 9,0 | 10,0 | 27,0 | 2,7 |

Vazão e utilização devem valer para as três políticas por conservação de
trabalho e simetria. O tempo de resposta esperado deve obedecer
aproximadamente:

```text
E[R]_FilaMaisCurta <= E[R]_RoundRobin <= E[R]_Aleatoria
```

Para cada `lambda`, calcular também o ganho percentual em relação à Aleatória:

```text
ganho_% = 100*(E[R]_aleatoria - E[R]_politica)/E[R]_aleatoria
```

## 8. Próximos commits recomendados

### Commit 1 - Serviço exponencial e configuração vigente - concluído

- substituir os padrões antigos por capacidade 1, `mu=1`, horizonte 5000 e
  warm-up 500;
- sortear duração exponencial com média `1/mu`;
- garantir sementes reproduzíveis;
- permitir injeção de duração determinística nos testes;
- atualizar testes de servidor, configuração, logs e invariantes.

**Pronto quando:** amostras são positivas, a média empírica se aproxima de 1,
a mesma semente reproduz os valores e os testes de FCFS continuam passando.

### Commit 2 - Observabilidade pública do servidor - concluído

- adicionar callbacks públicos de início e conclusão do serviço;
- ligar esses callbacks ao `MetricsCollector`;
- remover do notebook o monkey patch de `_resource`, `_record_state` e
  `_completed_count`.

**Pronto quando:** o ciclo `arrival -> routing -> service_started ->
service_completed` é coletado automaticamente em um teste de integração.

### Commit 3 - Políticas e balanceador alinhados

- separar as políticas em `policies.py`;
- validar servidores, ambientes e requisições;
- remover `**kwargs` da construção do balanceador;
- tornar aleatório o desempate de Fila Mais Curta;
- testar todos os empates e a reprodutibilidade.

### Commit 4 - Métricas temporais

- adicionar `E[N]` por integração da ocupação;
- adicionar `U_1`, `U_2` e `U_3` por integração do tempo ocupado;
- aplicar corretamente o recorte `[500, 5000)`;
- testar integrais com trajetórias pequenas calculadas manualmente.

### Commit 5 - Executor de uma rodada

Criar `simulation.py` para montar configuração, ambiente, três servidores,
balanceador, traço, coletor e logger. A execução deve retornar um objeto
imutável com métricas, eventos necessários e metadados da semente.

### Commit 6 - Experimentos estáveis

- executar as 150 rodadas;
- usar o mesmo traço nas três políticas de cada `(lambda, replica)`;
- salvar resultados individuais e agregados;
- calcular IC de 95%;
- verificar `X`, `U_i` e Lei de Little.

### Commit 7 - Modelo analítico e comparação

- implementar as fórmulas `M/M/1`;
- gerar automaticamente a tabela teórica;
- comparar `E[R]` simulado com a curva analítica;
- calcular ganhos de Round Robin e Fila Mais Curta.

### Commit 8 - Experimento instável

- executar `lambda=3,3`;
- registrar `N(t)`;
- comparar com a reta de inclinação `0,3`;
- deixar explícito que métricas estacionárias não se aplicam.

### Commit 9 - CLI, gráficos e documentação final

- comandos para uma rodada e para todos os experimentos;
- CSVs e gráficos reproduzíveis;
- execução conferida em Windows e Linux;
- README final e relatório IEEE.

## 9. Testes essenciais

### Serviço e servidor

- todo tempo exponencial sorteado é positivo;
- média empírica próxima de `1/mu`;
- mesma semente produz mesma sequência;
- capacidade ativa nunca excede 1;
- fila mantém ordem FCFS;
- uma função de duração determinística pode ser injetada nos testes.

### Políticas

- Aleatória é reproduzível e aproximadamente uniforme;
- Round Robin produz a sequência exata;
- Fila Mais Curta usa `active + waiting`;
- todos os servidores empatados participam do sorteio de desempate.

### Medição

- eventos anteriores a 500 não entram nas métricas;
- intervalos que cruzam 500 ou 5000 são recortados;
- `E[N]` é uma integral temporal;
- `0 <= U_i <= 1`;
- conservação de requisições continua válida;
- `E[N] ~= X*E[R]` dentro da incerteza estatística.

### Sanidade do sistema

- com `lambda` muito pequeno, `E[R]` tende a `E[S]=1` em qualquer política;
- na política Aleatória, os resultados convergem às fórmulas `M/M/1`;
- para `lambda<3`, vazão tende a `lambda`;
- para `lambda=3,3`, `N(t)` cresce aproximadamente a taxa 0,3.

## 10. Estrutura sugerida para o relatório

1. **Resumo:** sistema, políticas, simulação e principal conclusão.
2. **Arquitetura e metodologia:** três `M/M/1`, parâmetros, warm-up, réplicas,
   sementes e métricas temporais.
3. **Modelo analítico:** itens (a)-(f), incluindo splitting, estabilidade,
   fórmulas, Lei de Little e sobrecarga.
4. **Resultados:** tabela e gráfico de `E[R]`, IC de 95%, vazão, utilizações,
   `E[N]` e ganhos percentuais.
5. **Conclusão:** ordenação das políticas, estabilidade e limitações.
6. **Divisão do trabalho:** compatível com os commits da dupla.

Os resultados, tabelas e gráficos devem ser gerados pelo código para evitar
transcrição manual. O relatório deve usar o formato IEEE de duas colunas e ter
no máximo 4 páginas.

## 11. Divisão de trabalho e checklist

Uma divisão compatível com o histórico atual é:

- integrante responsável pela base: servidor, serviço exponencial, eventos,
  logs, métricas temporais, invariantes e testes correspondentes;
- outro integrante: políticas, tráfego Poisson, balanceador e testes;
- ambos: integração, protocolo experimental, modelo analítico, gráficos e
  relatório.

Checklist obrigatório:

- [x] 3 servidores homogêneos com uma unidade de serviço cada.
- [x] Filas FCFS ilimitadas.
- [x] Chegadas Poisson reproduzíveis.
- [x] Serviço exponencial com `mu=1`.
- [ ] Três políticas configuráveis e desempate correto.
- [ ] Horizonte 5000 e warm-up 500.
- [ ] Cinco taxas estáveis, três políticas e dez réplicas: 150 execuções.
- [ ] Média e IC de 95%.
- [ ] `X`, `E[R]`, `E[N]` temporal e `U_i`.
- [ ] Modelo analítico apenas da Aleatória, com três `M/M/1`.
- [ ] Comparação de `E[R]` e ganhos percentuais.
- [ ] Lei de Little conferida nas três políticas.
- [ ] Experimento instável com `lambda=3,3` e aproximação fluida.
- [ ] Logs detalhados de distribuição e ocupação.
- [ ] Testes automatizados e execução em Windows e Linux.
- [ ] Relatório IEEE com até 4 páginas.
- [ ] Divisão da dupla compatível com os commits.
