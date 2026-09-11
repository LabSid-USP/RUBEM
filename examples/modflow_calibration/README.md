# Configuração de Bauru para calibração do MODFLOW

`bauru_modflow_calibration.json` foi gerado a partir de
`D:/Bauru/bauru_modflow.json`. Os demais parâmetros, caminhos de entrada,
diretório de saída, GHB e opções do solver foram mantidos.

As constantes iniciais correspondem aos valores uniformes encontrados nos
mapas originais:

| Campo | Valor no JSON |
| --- | --- |
| `specific_storage`, em cada camada | `0.000001` |
| `specific_yield`, em cada camada | `0.15` |
| `river.layers[0].conductance` | `0.387` m²/dia por célula de rio |

Esses são valores iniciais para a calibração, não resultados calibrados.
`specific_storage` mantém a interpretação da entrada anterior: o código o
envia diretamente como armazenamento primário Sf1 ao BCF, sem conversão
adicional de espessura no RUBEM. Confira a convenção de armazenamento antes
de escolher os limites de calibração. Na camada superior com `laytype=1`,
é `specific_yield` que controla o armazenamento; alterar `specific_storage`
nessa camada não modifica a simulação.

## Mapas nominais e tabelas

Prepare três mapas PCRaster do tipo **Nominal**, com o mesmo clone das entradas:

| Camada (de baixo para cima) | Mapa configurado | Tabela |
| --- | --- | --- |
| 1 | `D:/Bauru/carol/input/modflow/kh_classes1.map` | `kh1.tbl` |
| 2 | `D:/Bauru/carol/input/modflow/kh_classes2.map` | `kh2.tbl` |
| 3 | `D:/Bauru/carol/input/modflow/kh_classes3.map` | `kh3.tbl` |

Esses mapas ainda não existiam quando o exemplo foi gerado. Você pode ajustar
os caminhos no JSON para usar seus próprios mapas de classes.

Cada tabela fornecida é um **modelo**, com duas classes ilustrativas:

```text
1 4.813
2 5.192
```

A primeira coluna é o ID nominal e a segunda é a condutividade horizontal
em m/dia, com `compute_conductivity=true`. Ajuste IDs e valores de cada tabela
às classes reais da respectiva camada. Os valores ilustrativos usam os
extremos encontrados nos mapas horizontais anteriores; a distribuição
espacial anterior não foi convertida nem reconstruída.

Todas as classes presentes nas células de `boundary != 0` precisam de um
valor positivo e finito. NoData ou classe sem correspondência em uma célula
dessas interrompe a inicialização, informando camada, linha e coluna.

Os caminhos das tabelas são relativos ao JSON. Ao mover o JSON para
`D:/Bauru`, copie também `kh1.tbl`, `kh2.tbl` e `kh3.tbl` para essa pasta,
ou ajuste os caminhos das tabelas no JSON.

## Rios

O campo `mask` reaproveita `D:/Bauru/carol/input/modflow/riv_cond.map`:
pixels positivos recebem a condutância constante `0.387`; zero, valores
negativos, NoData e células inativas do MODFLOW ficam sem condutância.
Os mapas de nível e fundo do rio continuam sendo usados.

## Execução

Após preparar os mapas nominais e ajustar as tabelas, no terminal com o
ambiente RUBEM ativado, a partir da raiz do repositório:

```powershell
rubem run -c examples/modflow_calibration/bauru_modflow_calibration.json
```

Para cada candidato da calibração, atualize números e tabelas antes de criar
e inicializar uma nova execução do modelo. Os parâmetros de camada são
carregados na inicialização. O leitor evita reutilizar tabelas antigas do
cache do PCRaster entre execuções no mesmo processo Python.

A validação deste exemplo verifica a estrutura do JSON e a resolução das
tabelas. Ela não atesta a convergência do modelo de Bauru: as condições
iniciais e os demais dados físicos ainda precisam estar consistentes.
