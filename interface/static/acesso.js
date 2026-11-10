"use strict";

function accessPage(modo = "entrar", mensagem = "") {
  const cadastro = modo === "cadastrar";
  return `
    <div class="access-shell">
      <a href="#entrar" class="access-brand" aria-label="Arvendro Gestão"><img src="/marca.svg" alt="Arvendro" width="230" height="54"><span>GESTÃO COMERCIAL</span></a>
      <section class="access-card" aria-label="Acesso ao sistema">
        <div class="access-heading"><h1>${cadastro ? "Criar conta" : "Entrar na sua conta"}</h1><p>${cadastro ? "Preencha os dados para cadastrar seu acesso." : "Use seu usuário e senha para acessar o sistema."}</p></div>
        <div class="access-switch" role="group" aria-label="Forma de acesso">
          <button type="button" data-access-mode="entrar" aria-pressed="${!cadastro}">Entrar</button>
          <button type="button" data-access-mode="cadastrar" aria-pressed="${cadastro}">Criar conta</button>
        </div>
        <form data-auth="${cadastro ? "cadastrar" : "entrar"}">
          ${cadastro ? '<div class="field"><label for="access-name">Nome completo</label><input id="access-name" name="nome" autocomplete="name" placeholder="Seu nome" maxlength="80" required></div>' : ""}
          <div class="field"><label for="access-user">Usuário</label><input id="access-user" name="usuario" autocomplete="username" placeholder="Seu usuário" minlength="3" maxlength="40" autocapitalize="none" spellcheck="false" ${cadastro ? 'aria-describedby="user-help"' : ""} required>${cadastro ? '<small id="user-help">De 3 a 40 caracteres. Use letras, números, ponto, traço ou sublinhado.</small>' : ""}</div>
          <div class="field"><label for="access-password">Senha</label><input id="access-password" name="senha" type="password" autocomplete="${cadastro ? "new-password" : "current-password"}" placeholder="${cadastro ? "Crie uma senha" : "Sua senha"}" ${cadastro ? 'minlength="8" aria-describedby="password-help"' : ""} maxlength="128" required>${cadastro ? '<small id="password-help">Use no mínimo 8 caracteres.</small>' : ""}</div>
          ${cadastro ? '<div class="field"><label for="access-confirmation">Confirmar senha</label><input id="access-confirmation" name="confirmacao" type="password" autocomplete="new-password" placeholder="Repita a senha" minlength="8" maxlength="128" required></div>' : ""}
          <label class="show-password"><input type="checkbox" id="show-password"> Mostrar senha</label>
          <p class="access-error" id="access-error" role="alert">${escapeHtml(mensagem)}</p>
          <button class="primary access-submit" type="submit">${cadastro ? "Cadastrar e entrar" : "Entrar no sistema"}</button>
        </form>
        <p class="access-alternative">${cadastro ? 'Já tem uma conta? <button type="button" data-access-mode="entrar">Entrar</button>' : 'Ainda não tem acesso? <button type="button" data-access-mode="cadastrar">Criar conta</button>'}</p>
      </section>
      <p class="access-footnote">Vendas, produtos e estoque em um único ambiente de trabalho.<br>As contas cadastradas compartilham os dados deste sistema.</p>
    </div>`;
}
