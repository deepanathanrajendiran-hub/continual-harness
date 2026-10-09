import pytest

from bench.evo import patch

CURL_GO = """FROM ubuntu:22.04
RUN apt-get update && apt-get install -y curl ca-certificates
RUN curl -fsSL https://go.dev/dl/go1.22.5.linux-amd64.tar.gz -o /tmp/go.tgz \\
    && tar -C /usr/local -xzf /tmp/go.tgz \\
    && rm /tmp/go.tgz
ENV PATH=/usr/local/go/bin:$PATH
"""

WGET_ARG_GO = """FROM ubuntu:22.04
ARG GO_VERSION=1.21.13
RUN apt-get update && apt-get install -y wget \\
 && wget -q https://dl.google.com/go/go${GO_VERSION}.linux-amd64.tar.gz \\
 && tar -C /usr/local -xzf go${GO_VERSION}.linux-amd64.tar.gz \\
 && rm go$GO_VERSION.linux-amd64.tar.gz
"""

YQ = """FROM ubuntu:22.04
RUN wget -qO /usr/local/bin/yq https://github.com/mikefarah/yq/releases/download/v4.44.3/yq_linux_amd64 \\
    && chmod +x /usr/local/bin/yq
RUN wget -qO- https://github.com/mikefarah/yq/releases/download/v4.44.3/yq_linux_amd64.tar.gz | tar xz \\
    && mv yq_linux_amd64 /usr/bin/yq
"""

DPKG_AWARE = """FROM ubuntu:22.04
RUN ARCH="$(dpkg --print-architecture)" \\
 && curl -fsSL "https://go.dev/dl/go1.22.5.linux-${ARCH}.tar.gz" | tar -C /usr/local -xz
"""

APT_GO = """FROM ubuntu:22.04
RUN apt-get update && apt-get install -y --no-install-recommends golang-go \\
    && rm -rf /var/lib/apt/lists/*
"""

GOARCH = """FROM ubuntu:22.04
ENV GOARCH=amd64
ENV GOARCH amd64
RUN CGO_ENABLED=0 GOARCH=amd64 go build -o /usr/local/bin/tool ./cmd/tool
"""

COMMENTED = """# syntax=docker/dockerfile:1
# Built for amd64 (x86_64) upstream.
FROM ubuntu:22.04
RUN apt-get update \\
# was: install the amd64 toolchain here
 && apt-get install -y make
"""


def test_curl_go_download_is_rewritten_to_arm64():
    text, changed = patch.arm_patch(CURL_GO)
    assert text == CURL_GO.replace("go1.22.5.linux-amd64.tar.gz", "go1.22.5.linux-arm64.tar.gz")
    assert changed == [
        "3: RUN curl -fsSL https://go.dev/dl/go1.22.5.linux-amd64.tar.gz -o /tmp/go.tgz \\"
        " -> RUN curl -fsSL https://go.dev/dl/go1.22.5.linux-arm64.tar.gz -o /tmp/go.tgz \\"
    ]


def test_wget_with_a_version_arg_is_rewritten_on_every_continuation_line():
    text, changed = patch.arm_patch(WGET_ARG_GO)
    assert text == WGET_ARG_GO.replace(".linux-amd64.tar.gz", ".linux-arm64.tar.gz")
    assert [c.split(":", 1)[0] for c in changed] == ["4", "5", "6"]
    assert "amd64" not in text


def test_yq_binary_and_tarball_are_rewritten():
    text, changed = patch.arm_patch(YQ)
    assert text == YQ.replace("yq_linux_amd64", "yq_linux_arm64")
    assert [c.split(":", 1)[0] for c in changed] == ["2", "4", "5"]


def test_goarch_settings_are_rewritten():
    text, changed = patch.arm_patch(GOARCH)
    assert text == ("FROM ubuntu:22.04\nENV GOARCH=arm64\nENV GOARCH arm64\n"
                    "RUN CGO_ENABLED=0 GOARCH=arm64 go build -o /usr/local/bin/tool ./cmd/tool\n")
    assert len(changed) == 3


@pytest.mark.parametrize("dockerfile", [DPKG_AWARE, APT_GO, COMMENTED])
def test_arch_aware_apt_and_commented_files_are_unchanged(dockerfile):
    assert patch.arm_patch(dockerfile) == (dockerfile, [])
    assert patch.needs_patch(dockerfile) is False


@pytest.mark.parametrize("dockerfile", [CURL_GO, WGET_ARG_GO, YQ, GOARCH])
def test_patching_is_idempotent(dockerfile):
    assert patch.needs_patch(dockerfile) is True
    once, changed = patch.arm_patch(dockerfile)
    assert changed
    assert patch.arm_patch(once) == (once, [])
    assert patch.needs_patch(once) is False


def test_line_endings_are_preserved():
    crlf = CURL_GO.replace("\n", "\r\n")
    text, _ = patch.arm_patch(crlf)
    assert text == crlf.replace("linux-amd64", "linux-arm64")


@pytest.mark.parametrize("line,lineno", [
    ("RUN curl -fsSLO https://github.com/protocolbuffers/protobuf/releases/download/v25.1/protoc-25.1-linux-x86_64.zip", 2),
    ("RUN wget https://releases.hashicorp.com/terraform/1.9.0/terraform_1.9.0_linux_amd64.zip", 2),
    ("ARG ARCH=amd64", 2),
    ("RUN dpkg --add-architecture amd64", 2),
    ("RUN echo ok \\\n && curl -fsSL https://example.com/tool-linux-amd64 -o /usr/local/bin/tool", 3),
])
def test_an_unknown_amd64_pattern_raises_with_its_line(line, lineno):
    with pytest.raises(patch.UnknownArchPattern) as err:
        patch.arm_patch(f"FROM ubuntu:22.04\n{line}\n")
    assert str(err.value).startswith(f"line {lineno}: ")
    assert "amd64" in str(err.value) or "x86_64" in str(err.value)


def test_an_unknown_pattern_in_the_same_run_as_a_go_download_still_raises():
    dockerfile = CURL_GO.replace("    && rm /tmp/go.tgz", "    && curl -fsSLO https://example.com/helper_amd64.deb")
    with pytest.raises(patch.UnknownArchPattern, match="^line 5: "):
        patch.arm_patch(dockerfile)


def test_from_an_amd64_platform_raises():
    with pytest.raises(patch.UnknownArchPattern, match="^line 1: "):
        patch.arm_patch("FROM --platform=linux/amd64 ubuntu:22.04\n")


@pytest.mark.parametrize("instruction", [
    "COPY go1.21.0.linux-amd64.tar.gz /tmp/",
    "COPY vendor/go1.21.0.linux-amd64.tar.gz /usr/local/",
    "ADD go1.21.0.linux-amd64.tar.gz /usr/local/",
])
def test_a_bundled_amd64_tarball_raises(instruction):
    with pytest.raises(patch.UnknownArchPattern, match="^line 2: .*bundled"):
        patch.arm_patch(f"FROM ubuntu:22.04\n{instruction}\n")


def test_add_of_a_go_url_is_rewritten():
    dockerfile = "FROM ubuntu:22.04\nADD https://go.dev/dl/go1.22.5.linux-amd64.tar.gz /tmp/go.tgz\n"
    text, changed = patch.arm_patch(dockerfile)
    assert text == dockerfile.replace("amd64", "arm64") and len(changed) == 1


def test_a_pinned_checksum_next_to_a_rewritten_artifact_raises():
    digest = "a" * 64
    dockerfile = ("FROM ubuntu:22.04\n"
                  "RUN curl -fsSLO https://go.dev/dl/go1.22.5.linux-amd64.tar.gz \\\n"
                  f' && echo "{digest}  go1.22.5.linux-amd64.tar.gz" | sha256sum -c - \\\n'
                  " && tar -C /usr/local -xzf go1.22.5.linux-amd64.tar.gz\n")
    with pytest.raises(patch.UnknownArchPattern, match="^line 3: .*sha256"):
        patch.arm_patch(dockerfile)


def test_a_checksum_in_an_untouched_instruction_is_fine():
    digest = "b" * 64
    dockerfile = CURL_GO + f'RUN echo "{digest}  other.tar.gz" > /tmp/sums\n'
    text, changed = patch.arm_patch(dockerfile)
    assert len(changed) == 1 and digest in text


def test_main_prints_the_changes_and_never_writes(tmp_path, capsys):
    path = tmp_path / "Dockerfile"
    path.write_text(CURL_GO)
    assert patch.main([str(path)]) == 0
    out = capsys.readouterr().out
    assert "linux-arm64" in out and out.startswith("3: ")
    assert path.read_text() == CURL_GO
    path.write_text(APT_GO)
    assert patch.main([str(path)]) == 0
    assert capsys.readouterr().out == "no change\n"
    path.write_text("FROM ubuntu:22.04\nARG ARCH=amd64\n")
    assert patch.main([str(path)]) == 2
    assert capsys.readouterr().err.startswith("line 2: ")


def test_a_bundled_go_tarball_is_swapped_for_the_verified_arm64_archive(tmp_path):
    import hashlib

    env = tmp_path / "environment"
    env.mkdir()
    (env / "go1.21.0.linux-amd64.tar.gz").write_bytes(b"amd64 toolchain")
    arm64 = b"arm64 toolchain"
    digest = hashlib.sha256(arm64).hexdigest()
    releases = [{"version": "go1.21.0", "files": [
        {"filename": "go1.21.0.linux-arm64.tar.gz", "os": "linux", "arch": "arm64", "sha256": digest}]}]
    got = []

    def download(url, dest):
        got.append(url)
        dest.write_bytes(arm64)

    dockerfile = ("FROM ubuntu:22.04\nCOPY go1.21.0.linux-amd64.tar.gz /tmp/\n"
                  "RUN tar -C /usr/local -xzf /tmp/go1.21.0.linux-amd64.tar.gz\n")
    text, artifacts = patch.replace_bundled_go(env, dockerfile, releases=lambda: releases, download=download)
    assert got == ["https://go.dev/dl/go1.21.0.linux-arm64.tar.gz"]
    assert sorted(p.name for p in env.iterdir()) == ["go1.21.0.linux-arm64.tar.gz"]
    assert artifacts == [{"line": 2, "file": "go1.21.0.linux-arm64.tar.gz", "replaces": "go1.21.0.linux-amd64.tar.gz",
                          "url": got[0], "sha256": digest}]
    patched, changed = patch.arm_patch(text)
    assert "amd64" not in patched and [c.split(":", 1)[0] for c in changed] == ["3"]
    (env / "go1.21.0.linux-amd64.tar.gz").write_bytes(b"amd64 toolchain")
    wrong = [{"files": [{"filename": "go1.21.0.linux-arm64.tar.gz", "sha256": "0" * 64}]}]
    with pytest.raises(patch.UnknownArchPattern, match="^line 2: .*sha256"):
        patch.replace_bundled_go(env, dockerfile, releases=lambda: wrong, download=download)
    assert (env / "go1.21.0.linux-amd64.tar.gz").is_file()


def test_no_bundled_tarball_means_no_network(tmp_path):
    def boom(*args, **kwargs):
        raise AssertionError("must not fetch")

    (tmp_path / "environment").mkdir()
    for dockerfile in ("FROM ubuntu:22.04\nCOPY go1.21.0.linux-amd64.tar.gz /tmp/\n",
                       "FROM ubuntu:22.04\nRUN curl -fsSLO https://go.dev/dl/go1.22.5.linux-amd64.tar.gz\n"):
        assert patch.replace_bundled_go(tmp_path / "environment", dockerfile, releases=boom, download=boom) == (
            dockerfile, [])

def test_a_tarball_path_outside_the_build_context_is_never_touched(tmp_path):
    def boom(*args, **kwargs):
        raise AssertionError("must not fetch")

    env = tmp_path / "ctx" / "environment"
    env.mkdir(parents=True)
    host = tmp_path / "go1.21.0.linux-amd64.tar.gz"
    host.write_bytes(b"a host file")
    (tmp_path / "ctx" / "go1.21.0.linux-amd64.tar.gz").write_bytes(b"next to the context")
    for token in (str(host), "../go1.21.0.linux-amd64.tar.gz"):
        dockerfile = f"FROM ubuntu:22.04\nCOPY {token} /tmp/\n"
        assert patch.replace_bundled_go(env, dockerfile, releases=boom, download=boom) == (dockerfile, [])
    assert host.read_bytes() == b"a host file"
    assert (tmp_path / "ctx" / "go1.21.0.linux-amd64.tar.gz").is_file()
