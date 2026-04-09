# Claude Code agent plugin.
# Wraps llm-agents.nix binary + our runner.py into one closure.
{ pkgs ? import <nixpkgs> {}
, claude-code-bin ? null  # pass from flake.nix
}:

let
  bin = if claude-code-bin != null then claude-code-bin
        else throw "claude-code-bin must be provided (from llm-agents.nix)";
in
pkgs.symlinkJoin {
  name = "agentix-plugin-claude-code";
  paths = [ bin ];
  postBuild = ''
    cp ${./runner.py} $out/runner.py
  '';
}
