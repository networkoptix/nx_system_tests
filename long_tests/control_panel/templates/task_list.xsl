<html xmlns:xsl="http://www.w3.org/1999/XSL/Transform" xsl:version="1.0">
    <head>
        <link rel="stylesheet" href="templates/task_table.css"/>
        <title>Comparison tests control panel</title>
    </head>
    <body>
        <h1>Tests</h1>
        <table>
            <thead>
                <tr>
                    <th>Started</th>
                    <th>Finished</th>
                    <th>Type</th>
                    <th>Status</th>
                    <th>Version</th>
                    <th>Installer type</th>
                    <th>Installer</th>
                    <th>Artifacts</th>
                </tr>
            </thead>
            <tbody>
                <xsl:for-each select="root/item[category='test']">
                    <tr>
                        <td><xsl:value-of select="started_at"/></td>
                        <td><xsl:value-of select="finished_at"/></td>
                        <td><xsl:value-of select="type"/></td>
                        <td class="{css_class}"><xsl:value-of select="task_status"/></td>
                        <td><xsl:value-of select="version"/></td>
                        <td><xsl:value-of select="installer_type"/></td>
                        <td><a href="{installers_url}" target="_blank"><xsl:value-of select="installers_url_text"/></a></td>
                        <td><a href="{artifacts_url}" target="_blank">Artifacts</a></td>
                    </tr>
                </xsl:for-each>
            </tbody>
        </table>
        <h1>Reports</h1>
        <table>
            <thead>
                <tr>
                    <th>Started</th>
                    <th>Finished</th>
                    <th>Type</th>
                    <th>Status</th>
                    <th>Description</th>
                </tr>
            </thead>
            <tbody>
                <xsl:for-each select="root/item[category='report']">
                    <tr>
                        <td><xsl:value-of select="started_at"/></td>
                        <td><xsl:value-of select="finished_at"/></td>
                        <td><xsl:value-of select="type"/></td>
                        <td class="{css_class}"><xsl:value-of select="task_status"/></td>
                        <td><code><xsl:value-of select="error"/></code></td>
                    </tr>
                </xsl:for-each>
            </tbody>
        </table>
    </body>
</html>
