import hashlib
import json
import logging
import shutil
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from pathlib import Path

from src.config import Pastas
from src.log_config import NOME_LOGGER
from src.repositorio_estoque import RepositorioEstoque
from src.validador import ErroValidacao, validar_venda

logger = logging.getLogger(NOME_LOGGER)


class Status(Enum):
    PROCESSADO = "processado"
    ERRO = "erro"
    DUPLICADO = "duplicado"


@dataclass(frozen=True)
class Resultado:
    arquivo: str
    status: Status
    motivo: str = ""


def _hash_conteudo(conteudo: bytes) -> str:
    return hashlib.sha256(conteudo).hexdigest()


def _mover(origem: Path, pasta_destino: Path) -> Path:
    """Move o arquivo sem sobrescrever outro de mesmo nome."""
    pasta_destino.mkdir(parents=True, exist_ok=True)
    destino = pasta_destino / origem.name
    if destino.exists():
        carimbo = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        destino = pasta_destino / f"{origem.stem}_{carimbo}{origem.suffix}"
    shutil.move(str(origem), str(destino))
    return destino


def processar_arquivo(caminho: Path, repositorio: RepositorioEstoque, pastas: Pastas) -> Resultado:
    """Processa UM arquivo da pasta de entrada (RF03, RF04 e RF05).

    Nunca levanta exceção: qualquer falha manda o arquivo para a pasta de erros
    e registra o motivo no log, para não travar a fila dos demais arquivos.
    """
    caminho = Path(caminho)
    nome = caminho.name

    try:
        conteudo = caminho.read_bytes()
        hash_arquivo = _hash_conteudo(conteudo)

        # RF05: duplicidade por hash do conteúdo
        motivo = repositorio.motivo_duplicidade(hash_arquivo)
        if motivo:
            return _rejeitar(caminho, pastas, Status.DUPLICADO, motivo)

        # RF03: JSON bem formado
        try:
            dados = json.loads(conteudo.decode("utf-8"))
        except ValueError as erro:  # inclui JSONDecodeError e UnicodeDecodeError
            return _rejeitar(caminho, pastas, Status.ERRO, f"JSON malformado: {erro}")

        # RF03: regras de negócio
        venda = validar_venda(dados, repositorio.produtos)

        # RF05: duplicidade por venda_id (mesma venda em arquivos diferentes)
        motivo = repositorio.motivo_duplicidade(hash_arquivo, venda.venda_id)
        if motivo:
            return _rejeitar(caminho, pastas, Status.DUPLICADO, motivo)

        # RF04: atualiza estoque + registra o arquivo (gravação atômica)
        repositorio.aplicar_venda(venda, nome, hash_arquivo)
        try:
            _mover(caminho, pastas.processados)
        except OSError as erro:
            # A baixa e o registro já foram persistidos. Não classificar como
            # rejeitada uma venda que já foi aplicada ao estoque.
            motivo = f"venda processada, mas não foi possível mover o arquivo: {erro}"
            logger.error("PROCESSADO COM AVISO | %s | %s", nome, motivo)
            return Resultado(nome, Status.PROCESSADO, motivo)
        resumo = ", ".join(f"produto {i.produto_id} -{i.quantidade}" for i in venda.itens)
        logger.info("PROCESSADO | %s | venda %s | %s", nome, venda.venda_id, resumo)
        return Resultado(nome, Status.PROCESSADO)

    except ErroValidacao as erro:
        return _rejeitar(caminho, pastas, Status.ERRO, str(erro))
    except Exception as erro:  # noqa: BLE001 - disponibilidade: não derrubar a fila
        logger.exception("Falha inesperada ao processar %s", nome)
        return _rejeitar(caminho, pastas, Status.ERRO, f"falha inesperada: {erro}")


def _rejeitar(caminho: Path, pastas: Pastas, status: Status, motivo: str) -> Resultado:
    nome = caminho.name
    try:
        _mover(caminho, pastas.erros)
    except OSError as erro:
        logger.error("Não foi possível mover %s para a pasta de erros: %s", nome, erro)
    rotulo = "DUPLICADO" if status is Status.DUPLICADO else "ERRO"
    logger.warning("%s | %s | %s", rotulo, nome, motivo)
    return Resultado(nome, status, motivo)


def processar_pendentes(repositorio: RepositorioEstoque, pastas: Pastas) -> list[Resultado]:
    """Processa todos os .json da pasta de entrada, em ordem de nome."""
    resultados = []
    for caminho in sorted(pastas.entrada.glob("*.json")):
        if caminho.is_file():
            resultados.append(processar_arquivo(caminho, repositorio, pastas))
    return resultados
