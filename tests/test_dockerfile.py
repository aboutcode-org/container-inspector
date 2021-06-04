#
# Copyright (c) nexB Inc. and others. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
# See http://www.apache.org/licenses/LICENSE-2.0 for the license text.
# See https://github.com/nexB/container-inspector for support or download.
# See https://aboutcode.org for more information about nexB OSS projects.
#

import os

from commoncode.testcase import FileBasedTesting

from container_inspector.dockerfile import normalized_layer_command


class TestDockerfile(FileBasedTesting):
    test_data_dir = os.path.join(os.path.dirname(__file__), 'data')

    def test_normalized_layer_command(self):
        # tuple of command and expected result tuples
        test_data = [
            ('#(nop) MAINTAINER The CentOS Project <cloud-ops@centos.org> - ami_creator ', ('MAINTAINER', 'The CentOS Project <cloud-ops@centos.org> - ami_creator')),
            ('#(nop) VOLUME ["/etc/elasticsearch"]', ('VOLUME', '["/etc/elasticsearch"]')),
            ('./usr/local/bin/run_rvm.sh', ('RUN', './usr/local/bin/run_rvm.sh')),
            ('', ('FROM', '')),
            (' ', ('FROM', '')),
            (None, ('FROM', '')),
            ('#(nop) ADD cacerts in /usr/java/openJDK-8-b132/jre/lib/security/cacerts', ('ADD', 'cacerts /usr/java/openJDK-8-b132/jre/lib/security/cacerts')),
            ('#(nop) CMD [/bin/sh -c supervisord -c /etc/supervisord.conf]', ('CMD', 'supervisord -c /etc/supervisord.conf')),
            ('#(nop)  ENV  CA_CERT_LOCATION=/etc/keys/ca.pem', ('ENV', 'CA_CERT_LOCATION=/etc/keys/ca.pem')),
            ('#(nop) EXPOSE map[7500/tcp:{}]', ('EXPOSE', 'map[7500/tcp:{}]')),
            ('#(nop) VOLUME ["/var/log", "/usr/local/pgsql/data"]', ('VOLUME', '["/var/log", "/usr/local/pgsql/data"]')),
            ('#(nop) WORKDIR /', ('WORKDIR', '/')),
        ]
        for layer_command, expected in test_data:
            assert expected == normalized_layer_command(layer_command)
