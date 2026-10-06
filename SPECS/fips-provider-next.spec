## START: Set by rpmautospec
## (rpmautospec version 0.8.4)
## RPMAUTOSPEC: autorelease, autochangelog
%define autorelease(e:s:pb:n) %{?-p:0.}%{lua:
    release_number = 5;
    base_release_number = tonumber(rpm.expand("%{?-b*}%{!?-b:1}"));
    print(release_number + base_release_number - 1);
}%{?-e:.%{-e*}}%{?-s:.%{-s*}}%{!?-n:%{?dist}}
## END: Set by rpmautospec

%bcond check 1

%define osslver 4.0.1

%global crate kryoptic

%define srpmhash() %{lua:
local files = rpm.expand("%_specdir/fips-provider-next.spec")
for i, p in ipairs(patches) do
   files = files.." "..p
end
for i, p in ipairs(sources) do
   files = files.." "..p
end
local sha256sum = assert(io.popen("cat "..files.." 2>/dev/null | sha256sum"))
local hash = sha256sum:read("*a")
sha256sum:close()
print(string.sub(hash, 0, 16))
}

Name:           fips-provider-next
Version:        1.5.2
Release:        %autorelease
Summary:        A FIPS provider built from the Kryoptic project

License:        GPL-3.0-or-later and Apache-2.0
URL:            https://github.com/latchset/kryoptic
Source0:        kryoptic-%{version}.tar.gz
Source1:        kryoptic-vendor-%{version}.tar.gz
Source2:        openssl-%{osslver}.tar.gz
Source3:        fips-hmacify.sh

%if 0%{?rhel}
BuildRequires:  rust-toolset
%else
BuildRequires:  cargo-rpm-macros
%endif
BuildRequires:  gcc clang
BuildRequires:  coreutils, perl-interpreter, sed, zlib-devel, /usr/bin/cmp
BuildRequires:  perl(Test::Harness), perl(Test::More), perl(Math::BigInt)
BuildRequires:  perl(Module::Load::Conditional), perl(File::Temp) perl(Time::Piece)
BuildRequires:  perl(Time::HiRes), perl(IPC::Cmd), perl(Pod::Html), perl(Digest::SHA)
BuildRequires:  perl(FindBin), perl(lib), perl(File::Compare), perl(File::Copy), perl(bigint)

Conflicts:      openssl-fips-provider
Conflicts:      openssl-fips-provider-so
Provides:       fips-provider-so

Patch100:       0001-Prevent-test-deadlocks-in-synchronization.patch
Patch200:       openssl-%{osslver}-kryoptic.patch

%description
This package provides a cryptographic module that is both an OpenSSL provider
as well as a PKCS#11 software token. This is a preview of the next FIPS
validation.

%files
%{_libdir}/ossl-modules/fips.so
%{_libdir}/pkcs11/fipstokn.so
%license LICENSE.txt
%license LICENSE.dependencies

%prep
# Preps kryoptic
%setup -n kryoptic-%{version} -q
%autopatch -p1 -M 199
%setup -n kryoptic-%{version} -q -T -D -a 1
%cargo_prep -v vendor

# Preps openssl
%setup -n kryoptic-%{version} -q -T -D -a 2
pushd openssl-%{osslver}
%autopatch -p1 -m 200

%build
# Figure out which flags we want to use.
# default
sslarch=%{_os}-%{_target_cpu}
%ifarch x86_64
sslflags=enable-ec_nistp_64_gcc_128
%endif
%ifarch s390x
sslarch="linux64-s390x"
sslflags=no-ec_nistp_64_gcc_128
%endif
%ifarch aarch64
sslarch="linux-aarch64"
sslflags=enable-ec_nistp_64_gcc_128
%endif
%ifarch ppc64le
sslarch="linux-ppc64le"
sslflags=enable-ec_nistp_64_gcc_128
%endif
# The following is needed for EL9 which still builds i686
%ifarch %ix86
sslarch=linux-elf
%endif

# Add -Wa,--noexecstack here so that libcrypto's assembler modules will be
# marked as not requiring an executable stack.
# Also add -DPURIFY to make using valgrind with openssl easier as we do not
# want to depend on the uninitialized memory as a source of entropy anyway.
RPM_OPT_FLAGS="$RPM_OPT_FLAGS -Wa,--noexecstack -Wa,--generate-missing-build-notes=yes -DPURIFY $RPM_LD_FLAGS -Wl,--allow-multiple-definition"

pushd openssl-%{osslver}

./Configure \
    --prefix=%{_prefix} --openssldir=%{_sysconfdir}/pki/tls \
    ${sslflags} enable-fips \
    no-deprecated no-legacy no-tests \
    no-atexit no-comp no-egd no-ui-console \
    no-dgram no-http no-ssl-trace no-sock no-srtp \
    no-dtls no-dtls1-method no-dtls1_2-method \
    no-tls no-tls1-method no-tls1_1-method no-tls1_2-method \
    no-aria no-argon2 no-blake2 no-camellia no-cast no-chacha \
    no-des no-dsa no-ec2m no-gost no-idea no-ktls no-mdc2 \
    no-md4 no-poly1305 no-rc2 no-rc4 no-rc5 no-rmd160 no-seed no-siphash \
    no-sm2 no-sm2-precomp no-sm3 no-sm4 no-whirlpool \
    ${sslarch} $RPM_OPT_FLAGS \
    -DDEVRANDOM='"\"/dev/urandom\""' \
    -DOPENSSL_PEDANTIC_ZEROIZATION \
    -DKRYOPTIC_FIPS_VENDOR='"\"Red Hat Enterprise Linux FIPS Provider\""' \
    -DKRYOPTIC_FIPS_VERSION='"\"%{version}\""' \
    -DKRYOPTIC_FIPS_BUILD='"\"%{srpmhash}\""'

#Log selection in build logs
perl configdata.pm --dump

make

popd


export KRYOPTIC_OPENSSL_SOURCES=${PWD}/openssl-%{osslver}
%cargo_build -- --no-default-features --features fips,nssdb,ossl400
%{cargo_license_summary}
%{cargo_license} > LICENSE.dependencies
%{cargo_vendor_manifest}

%if %{with check}
%check
export KRYOPTIC_OPENSSL_SOURCES=${PWD}/openssl-%{osslver}
%cargo_test -- --no-default-features --features fips,nssdb,ossl400
%endif

%define __spec_install_post \
    %{?__debug_package:%{__debug_install_post}} \
    %{__arch_install_post} \
    %{__os_install_post} \
    pushd openssl-%{osslver} \
    %{SOURCE3} $RPM_BUILD_ROOT/%{_libdir}/ossl-modules/fips.so \
%{nil}

%install
mkdir -p -m755 $RPM_BUILD_ROOT%{_libdir}/ossl-modules
install -m755 target/release/libkryoptic_pkcs11.so $RPM_BUILD_ROOT/%{_libdir}/ossl-modules/fips.so
mkdir -p -m755 $RPM_BUILD_ROOT%{_libdir}/pkcs11
ln -s ../ossl-modules/fips.so $RPM_BUILD_ROOT%{_libdir}/pkcs11/fipstokn.so

%changelog
## START: Generated by rpmautospec
* Fri Aug 07 2026 Simo Sorce <simo@redhat.com> - 1.5.2-5
- Fix peformance regression with RSA key import

* Thu Jul 23 2026 Simo Sorce <simo@redhat.com> - 1.5.2-4
- Add patch to defer self-test by default

* Thu Jul 23 2026 Simo Sorce <simo@redhat.com> - 1.5.2-3
- Add patch that fixes a deadlock in the test suite

* Thu Jul 23 2026 Simo Sorce <simo@redhat.com> - 1.5.2-2
- Add RPM_OPT_FLAGS back

* Tue Jun 30 2026 Simo Sorce <simo@redhat.com> - 1.5.2-1
- Update to Kryoptic 1.5.2

* Wed Apr 01 2026 Simo Sorce <simo@redhat.com> - 1.5.0-7
- Fix a bug in one of the FIPS patches

* Wed Mar 25 2026 Simo Sorce <simo@redhat.com> - 1.5.0-6
- Add fix for getrandom flag in fips mode

* Wed Mar 11 2026 Simo Sorce <simo@redhat.com> - 1.5.0-5
- Add missing indicator for SLH-DSA signature test facility

* Wed Mar 11 2026 Simo Sorce <simo@redhat.com> - 1.5.0-4
- Add patch to zeroize memory in TLS KDF

* Tue Mar 10 2026 Simo Sorce <simo@redhat.com> - 1.5.0-3
- Update openssl code to 4.0.0 Alpha1

* Fri Mar 06 2026 Simo Sorce <simo@redhat.com> - 1.5.0-2
- Update openssl patch to handle FIPS-714

* Thu Mar 05 2026 Simo Sorce <simo@redhat.com> - 1.5.0-1
- Update to v1.5.0

* Fri Oct 03 2025 Simo Sorce <simo@redhat.com> - 1.2.0-3
- Add OpenSSL patch to fix RSA X.931 padding check

* Mon Sep 08 2025 Simo Sorce <simo@redhat.com> - 1.2.0-2
- Fix FIPS module name/version

* Wed Jul 23 2025 Simo Sorce <simo@redhat.com> - 1.2.0-1
- Initial commit on c10s
## END: Generated by rpmautospec
