{
  description = "Agentix: Coding Agent SDK — middleware for agent packaging, execution, and trajectory collection";

  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/nixos-unstable";
    llm-agents.url = "github:numtide/llm-agents.nix";
  };

  outputs = { self, nixpkgs, llm-agents }:
    let
      system = "x86_64-linux";
      pkgs = import nixpkgs { inherit system; };
      python = pkgs.python312;
      agentPkgs = llm-agents.packages.${system};
    in
    {
      # ── Packages ────────────────────────────────────────────────
      packages.${system} = {
        # Runtime server
        runtime = import ./runtime/default.nix { inherit pkgs; };

        # Agent plugins: llm-agents.nix binary + our runner.py
        claude-code = import ./agents/claude-code/default.nix {
          inherit pkgs;
          claude-code-bin = agentPkgs.claude-code;
        };
      };

      # ── Dev shell ───────────────────────────────────────────────
      devShells.${system}.default = pkgs.mkShell {
        packages = [
          python
          pkgs.uv
          pkgs.ruff
          python.pkgs.pytest
          python.pkgs.pytest-asyncio
          python.pkgs.fastapi
          python.pkgs.uvicorn
          python.pkgs.pydantic
          python.pkgs.python-multipart
          python.pkgs.httpx
          pkgs.nodejs_22
          pkgs.docker
        ];

        shellHook = ''
          echo "Agentix dev shell"
          echo "  python: $(python3 --version)"
          echo "  ruff:   $(ruff --version)"
          echo ""
          echo "Commands:"
          echo "  python -m agentix.runtime --plugin <path>   # run server"
          echo "  nix build .#runtime                         # build runtime"
          echo "  nix build .#claude-code                     # build plugin"
        '';
      };
    };
}
