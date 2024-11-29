<html xmlns:xsl="http://www.w3.org/1999/XSL/Transform" xsl:version="1.0">
    <head>
        <link rel="stylesheet" href="/templates/main.css"/>
        <title><xsl:value-of select="root/header/title"/></title>
    </head>
    <body>
        <header>
            <h1>Select TestRail project</h1>
            <h2>TestRail cache synchronized: <xsl:value-of select="root/header/cache_age"/></h2>
        </header>
        <br class="page-action-clear"/>
        <table>
            <thead>
                <tr>
                    <th>Project name</th>
                    <th>Type</th>
                    <th>Name</th>
                </tr>
                </thead>
                <tbody>
                    <xsl:for-each select="root/rows/item">
                    <tr>
                        <td>
                            <xsl:value-of select="project/name"/>
                        </td>
                        <td>
                            <xsl:value-of select="phase/type"/>
                        </td>
                        <td>
                            <a href="{phase/url}"><xsl:value-of select="phase/name"/></a>
                        </td>
                    </tr>
                    </xsl:for-each>
                </tbody>
        </table>
    </body>
</html>
