<html xmlns:xsl="http://www.w3.org/1999/XSL/Transform" xsl:version="1.0">
    <head>
        <link rel="stylesheet" href="/templates/tasks.css"/>
        <link rel="stylesheet" href="/templates/table.css"/>
    </head>
    <body>
        <h1><xsl:value-of select="root/app_name"/> tasks:</h1>
        <xsl:for-each select="root/task_tables/item">
        <h2>Task group <a href="{./href}"><xsl:value-of select="./name"/></a></h2>
        <table>
            <thead>
                <tr>
                    <th>Task ID</th>
                    <th>Status</th>
                    <th>Artifacts</th>
                    <th>Script args</th>
                </tr>
            </thead>
            <tbody>
                <xsl:for-each select="./tasks/item">
                <tr>
                    <td><xsl:value-of select="id"/></td>
                    <td class="{status/class}"><xsl:value-of select="status/text"/></td>
                    <td>
                        <xsl:if test="artifacts">
                        <a href="{artifacts/href}"><xsl:value-of select="artifacts/url"/></a>
                        </xsl:if>
                    </td>
                    <td><pre><xsl:value-of select="script_args"/></pre></td>
                </tr>
                </xsl:for-each>
            </tbody>
        </table>
        </xsl:for-each>
    </body>
</html>
