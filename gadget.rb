class Gadget < Formula
  include Language::Python::Virtualenv

  desc "PlatformZero Gadget Utility"
  homepage "https://bitbucket.org/capcosaas/pz-gadget"
  url "https://github.com/Azure/azure-cli/archive/azure-cli-2.29.0.tar.gz"
  sha256 "b282d31ad5a87a187049ec3bdc4bbc965dbd651c47f97d0f0e383fb0cbf0f9c0"
  license "Proprietary"
  head "https://bitbucket.org/capcosaas/pz-gadget.git", branch: "dev"

  livecheck do
    url :stable
    strategy :github_latest
    regex(%r{href=.*?/tag/azure-cli[._-]v?(\d+(?:\.\d+)+)["' >]}i)
  end

  bottle do
    sha256 cellar: :any,                 arm64_big_sur: "f822e4b652faff8456fce66079266d55c90d39f6dea3ecfa15eb422aef250c83"
    sha256 cellar: :any,                 big_sur:       "7dca5295f8c4469b1124eaf2ddb73ffa046f6b06a02ce8b8112261168d105e78"
    sha256 cellar: :any,                 catalina:      "83bd565174fccd898a75397c95c74716977c029b08406ea3ecaa2b8957ca895a"
    sha256 cellar: :any,                 mojave:        "32377a40740baae1668c51adee3bda1b6d0a31684d946d68550f5ea434927240"
    sha256 cellar: :any_skip_relocation, x86_64_linux:  "673c3d103b164cf4abb63e8ea4396366c26672ce9bdcf500b4f76d7a5971ae0c"
  end

  depends_on "openssl@1.1"
  depends_on "python@3.9"

  uses_from_macos "libffi"

  on_linux do
    depends_on "pkg-config" => :build
  end

  def install
    virtualenv_install_with_resources
  end
  
  def install
    venv = virtualenv_create(libexec, "python3", system_site_packages: false)
    venv.pip_install resources

    # Get the CLI components we'll install
    # components = [
    #   buildpath/"src/azure-cli",
    #   buildpath/"src/azure-cli-telemetry",
    #   buildpath/"src/azure-cli-core",
    # ]

    # Install CLI
    components.each do |item|
      cd item do
        venv.pip_install item
      end
    end

    # (bin/"az").write <<~EOS
    #   #!/usr/bin/env bash
    #   AZ_INSTALLER=HOMEBREW #{libexec}/bin/python -m azure.cli \"$@\"
    # EOS

    # bash_completion.install "az.completion" => "az"
  end

  # test do
  #   json_text = shell_output("#{bin}/az cloud show --name AzureCloud")
  #   azure_cloud = JSON.parse(json_text)
  #   assert_equal azure_cloud["name"], "AzureCloud"
  #   assert_equal azure_cloud["endpoints"]["management"], "https://management.core.windows.net/"
  #   assert_equal azure_cloud["endpoints"]["resourceManager"], "https://management.azure.com/"
  # end
end
