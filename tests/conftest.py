import pytest


@pytest.fixture
def wikiaves_species_html():
    """HTML mínimo simulando uma página de espécie do WikiAves."""
    return """
    <html>
    <head>
        <title>WikiAves - Bem-te-vi (Pitangus sulphuratus)</title>
        <meta property="og:image" content="https://www.wikiaves.com.br/img/bemtevi.jpg" />
    </head>
    <body>
        <table id="taxonomia">
            <tr><td>Reino:</td><td>Animalia</td></tr>
            <tr><td>Filo:</td><td>Chordata</td></tr>
            <tr><td>Classe:</td><td>Aves</td></tr>
            <tr><td>Ordem:</td><td>Passeriformes</td></tr>
            <tr><td>Família:</td><td>Tyrannidae</td></tr>
        </table>

        <h2>Nome Científico</h2>
        <i>Pitangus sulphuratus</i>
        <sup>(Linnaeus, 1766)</sup>
        <h2>Nome em Inglês</h2>
        Great Kiskadee
        <h2>Estado de Conservação</h2>
        <a href="#">Pouco Preocupante</a>

        <h2 id="caracteristicas">Características</h2>
        <p>Mede 23,5 centímetros de comprimento e pesa de 52 a 68 gramas.</p>

        <h2 id="alimentacao">Alimentação</h2>
        <p>Onívoro, alimenta-se de insetos, frutas e pequenos vertebrados.</p>

        <h2 id="reproducao">Reprodução</h2>
        <p>Constrói ninho fechado com entrada lateral.</p>

        <h2 id="habitos">Hábitos</h2>
        <p>Ave bastante comum e adaptável a ambientes urbanos.</p>

        <h2 id="distribuicao_geografica">Distribuição Geográfica</h2>
        <p>Presente em todo o Brasil.</p>

        <div class="wa-galeria">
            <a class="wa-wikifoto" href="/foto/12345">Foto 1</a>
            <a class="wa-wikifoto" href="https://www.wikiaves.com.br/foto/67890">Foto 2</a>
            <a class="wa-wikifoto" href="/foto/11111">Foto 3</a>
        </div>
    </body>
    </html>
    """


@pytest.fixture
def wikiaves_table_html():
    """HTML mínimo simulando a tabela de espécies do WikiAves."""
    return """
    <html><body>
    <table class="wa-table-sp">
    <tbody>
        <tr>
            <td>Tyrannidae</td>
            <td><a href="/wiki/Bem-te-vi"><i>Pitangus sulphuratus</i></a></td>
            <td>Bem-te-vi</td>
            <td><a href="/sons.php?s=123">15</a></td>
            <td><a href="/fotos.php?s=123">200</a></td>
        </tr>
        <tr>
            <td>\xa0</td>
            <td><a href="/wiki/Suiriri"><i>Tyrannus melancholicus</i></a></td>
            <td>Suiriri</td>
            <td><a href="/sons.php?s=456">10</a></td>
            <td><a href="/fotos.php?s=456">150</a></td>
        </tr>
    </tbody>
    </table>
    </body></html>
    """
