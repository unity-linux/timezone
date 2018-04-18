%define epoch	6
%define version	2018d

%define tzdata_version %{version}
%define tzcode_version 2018d

# the zic(8) and zdump(8) manpages are already in man-pages
%define build_manpages 0
%ifarch %mips 
%define build_java 0
%else
%define build_java 1
%endif

%define build_java8 0
%ifnarch %mips
%define build_java8 1
%endif

Summary:	Timezone data
Name:		timezone
Epoch:		%{epoch}
Version:	%{version}
Release:	%mkrel 2
License:	GPL
Group:		System/Base
Source0:	ftp://ftp.iana.org/tz/releases/tzdata%{tzdata_version}.tar.gz
Source1:	ftp://ftp.iana.org/tz/releases/tzcode%{tzcode_version}.tar.gz
Source2:	javazic.tar.gz
Source4:	javazic-1.8-37392f2f5d59.tar.xz
Patch1:		tzdata-extra-tz-links.patch
Patch2:		javazic-fixup.patch
Patch3:		javazic-exclusion-fix.patch
Provides:	tzdata = %{version}-%{release}
Requires(post):	coreutils
BuildRequires:	gawk
BuildRequires:	perl

%description
This package contains data files with rules for various timezones
around the world.

%if %{build_java}
%package java
Summary:	Timezone data for Java
Group:		System/Base
Provides:	tzdata-java = %{version}-%{release}
BuildRequires:	javapackages-tools
BuildRequires:  java-devel
%if %{build_java8}
BuildRequires:	java-1.8.0-devel
BuildArch:	noarch
%endif

%description java
This package contains timezone information for use by Java runtimes.
%endif

%prep
%setup -q -c -a 1
%patch1 -p1 -b .extra-tz-links

%if %{build_java}
mkdir javazic
tar xf %{SOURCE2} -C javazic
pushd javazic
%patch2 -p0 -b .javazic-fixup
%patch3
# Hack alert! sun.tools may be defined and installed in the
# VM. In order to guarantee that we are using IcedTea/OpenJDK
# for creating the zoneinfo files, rebase all the packages
# from "sun." to "rht.". Unfortunately, gcj does not support
# any of the -Xclasspath options, so we must go this route
# to ensure the greatest compatibility.
mv sun rht
for f in `find . -name '*.java'`; do
        sed -i -e 's:sun\.tools\.:rht.tools.:g'\
               -e 's:sun\.util\.:rht.util.:g' $f
done
popd

%if %{build_java8}
tar xf %{SOURCE4}
%endif

echo "tzdata%{tzdata_version}" >> VERSION

# Create zone.info entries for deprecated zone names (#40184)
	chmod +w zone.tab
	echo '# zone info for backward zone names' > zone.tab.new
	while read link cur old x; do
		case $link-${cur+cur}-${old+old}${x:+X} in
		Link-cur-old)
			awk -v cur="$cur" -v old="$old" \
				'!/^#/ && $3 == cur { sub(cur,old); print }' \
				zone.tab || echo ERROR ;;
		Link-*)
			echo 'Error processing backward entry for zone.tab'
			exit 1 ;;
		esac
	done < backward >> zone.tab.new
	if grep -q '^ERROR' zone.tab.new || ! cat zone.tab.new >> zone.tab; then
		echo "Error adding backward entries to zone.tab"
		exit 1
	fi
	rm -f zone.tab.new
%endif

%build

%make_build TZDIR=%{_datadir}/zoneinfo CFLAGS="%{optflags} -std=gnu99"

grep -v tz-art.htm tz-link.html > tz-link.html.new
mv -f tz-link.html.new tz-link.html

%if %{build_java}
FILES="africa antarctica asia australasia europe northamerica pacificnew
       southamerica backward etcetera systemv"

# Java 6/7 tzdata
pushd javazic
%{javac} -source 1.5 -target 1.5 -classpath . `find . -name \*.java`
popd
%{java} -classpath javazic/ rht.tools.javazic.Main -V %{version} \
  -d javazi \
  $FILES javazic/tzdata_jdk/gmt javazic/tzdata_jdk/jdk11_backward

%if %{build_java8}
# Java 8 tzdata
pushd javazic-1.8
%{javac} -source 1.8 -target 1.8 -classpath . `find . -name \*.java`
popd

%{java} -classpath javazic-1.8 build.tools.tzdb.TzdbZoneRulesCompiler \
    -srcdir . -dstfile tzdb.dat \
    -verbose \
    $FILES javazic-1.8/tzdata_jdk/gmt javazic-1.8/tzdata_jdk/jdk11_backward
%endif
%endif

%install
%__make TOPDIR=%{buildroot} \
     TZDIR=%{buildroot}%{_datadir}/zoneinfo \
     ETCDIR=%{buildroot}%{_sbindir} \
     install
rm -f %{buildroot}%{_datadir}/zoneinfo-posix
ln -s . %{buildroot}%{_datadir}/zoneinfo/posix
mv %{buildroot}%{_datadir}/zoneinfo-leaps %{buildroot}%{_datadir}/zoneinfo/right

# nuke unpackaged files
rm -f %{buildroot}%{_datadir}/zoneinfo/localtime
rm -f %{buildroot}%{_bindir}/tzselect
rm -rf %{buildroot}/usr/lib
rm -rf %{buildroot}%{_mandir}

%if %{build_java}
cp -a javazi %{buildroot}%{_datadir}/javazi
%if %{build_java8}
mkdir -p %{buildroot}%{_datadir}/javazi-1.8
install -p -m 644 tzdb.dat %{buildroot}%{_datadir}/javazi-1.8/
%endif
%endif

# install man pages
%if %{build_manpages}
mkdir -p %{buildroot}%{_mandir}/man8
for f in zic zdump; do
install -m 644 $f.8 %{buildroot}%{_mandir}/man8/
done
%endif

%triggerun -- %{name} < 6:2016i-4
# (cg) Transition to symlinked localtime file
if [ ! -L %{_sysconfdir}/localtime -a -f %{_sysconfdir}/sysconfig/clock ]; then
	# Read zone info from (now legacy sysconfig/clock)
	# (the symlink destination is now the canonical way of finding out which
	# timezone we are in)
	unset ZONE
	. %{_sysconfdir}/sysconfig/clock

	if [ -z "$ZONE" ]; then
		ZONE=UTC
	fi

	if [ -f %{_datadir}/zoneinfo/$ZONE ]; then
		ln -sf %{_datadir}/zoneinfo/$ZONE %{_sysconfdir}/localtime
	fi
fi
if [ ! -L %{_sysconfdir}/localtime -a -f %{_datadir}/zoneinfo/UTC ]; then
	ln -sf %{_datadir}/zoneinfo/UTC %{_sysconfdir}/localtime
fi

%files
%doc README
%doc theory.html
%doc tz-link.html
%{_bindir}/zdump
%{_sbindir}/zic
%if %{build_manpages}
%{_mandir}/man3/newctime.3*
%{_mandir}/man3/newtzset.3*
%{_mandir}/man5/tzfile.5*
%{_mandir}/man8/zdump.8*
%{_mandir}/man8/zic.8*
%endif
%dir %{_datadir}/zoneinfo
%{_datadir}/zoneinfo/*
%config(noreplace) %{_sysconfdir}/localtime

%if %{build_java}
%files java
%{_datadir}/javazi
%if %{build_java8}
%{_datadir}/javazi-1.8
%endif
%endif
